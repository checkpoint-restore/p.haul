#
# ploop disk hauler
#

import logging
import os
import shutil
import threading

import libploop

import iters
import mstats


DDXML_FILENAME = "DiskDescriptor.xml"


def get_ddxml_path(path):
	"""Get path to disk descriptor file by path to disk delta or directory"""
	p = path if os.path.isdir(path) else os.path.dirname(path)
	return os.path.join(p, DDXML_FILENAME)


def get_delta_abspath(delta_path, ct_priv):
	"""Transform delta path to absolute form

	If delta path starts with a slash it is already in absolute form,
	otherwise it is relative to containers private.
	"""

	if delta_path.startswith("/"):
		return delta_path
	else:
		return os.path.join(ct_priv, delta_path)


def merge_ploop_snapshot(ddxml, guid):
	libploop.snapshot(ddxml).delete(guid)


class shared_ploop(object):
	def __init__(self, path):
		self.__backup_ddxml = get_ddxml_path(path) + ".copy"
		self.__orig_ddxml = get_ddxml_path(path)

	def prepare(self):
		shutil.copyfile(self.__orig_ddxml, self.__backup_ddxml)
		self.__orig_guid = libploop.snapshot(
			self.__orig_ddxml).create_offline()
		self.__backup_guid = libploop.snapshot(self.__backup_ddxml).create()

	def restore(self):
		if self.__backup_guid:
			os.rename(self.__backup_ddxml, self.__orig_ddxml)
			merge_ploop_snapshot(self.__orig_ddxml, self.__backup_guid)

	def cleanup(self):
		if self.__orig_guid:
			# TODO(dguryanov) add delta removing when igor add it to libploop
			os.remove(self.__backup_ddxml)
			os.remove(self.__backup_ddxml + ".lck")

	def get_orig_info(self):
		return {"ddxml": self.__orig_ddxml, "guid": self.__orig_guid}


class p_haul_fs(object):
	def __init__(self, deltas, ct_priv):
		"""Initialize ploop disks hauler

		For each disk create libploop.ploopcopy object using path to disk
		descriptor file and corresponding socket.
		"""

		# Create libploop.ploopcopy objects, one per active ploop delta
		self.__log_init_hauler(deltas)
		self.__ct_priv = ct_priv
		self.__shared_ploops = []
		self.__ploop_copies = []
		for delta_path, delta_fd in deltas:
			ddxml_path = get_ddxml_path(delta_path)
			self.__check_ddxml(ddxml_path)
			self.__ploop_copies.append(
				libploop.ploopcopy(ddxml_path, delta_fd))

	def __parse_shared_ploops(self, shareds):
		if not shareds:
			return []
		return (get_delta_abspath(s, self.__ct_priv)
				for s in shareds.split(","))

	def set_options(self, opts):
		if iters.is_live_mode(opts.get("mode", None)):
			shareds = self.__parse_shared_ploops(opts.get("vz_shared_disks"))
			for shared in shareds:
				self.__shared_ploops.append(shared_ploop(shared))

	def set_work_dir(self, wdir):
		pass

	def start_migration(self):
		total_xferred = 0
		for ploopcopy in self.__ploop_copies:
			total_xferred += ploopcopy.copy_start()
		return mstats.fs_iter_stats(total_xferred)

	def next_iteration(self):
		total_xferred = 0
		for ploopcopy in self.__ploop_copies:
			total_xferred += ploopcopy.copy_next_iteration()
		return mstats.fs_iter_stats(total_xferred)

	def stop_migration(self):
		total_xferred = 0
		for ploopcopy in self.__ploop_copies:
			total_xferred += ploopcopy.copy_stop()

		for pl in self.__shared_ploops:
			pl.prepare()

		return mstats.fs_iter_stats(total_xferred)

	def restore_shared_ploops(self):
		for pl in self.__shared_ploops:
			pl.restore()

	def cleanup_shared_ploops(self):
		for pl in self.__shared_ploops:
			pl.cleanup()

	def prepare_src_data(self, data):
		if self.__shared_ploops:
			data["shareds"] = []
			for pl in self.__shared_ploops:
				data["shareds"].append(pl.get_orig_info())
		return data

	def persistent_inodes(self):
		"""Inode numbers do not change during ploop disk migration"""
		return True

	def __log_init_hauler(self, deltas):
		logging.info("Initialize ploop hauler")
		for delta in deltas:
			logging.info("\t`- %s", delta[0])

	def __check_ddxml(self, ddxml_path):
		"""Check disk descriptor file exist"""
		if not os.path.isfile(ddxml_path):
			raise Exception("{0} file missing".format(ddxml_path))


class p_haul_fs_receiver(object):
	def __init__(self, deltas):
		"""Initialize ploop disks receiver

		For each disk create delta receiver object using path to active delta
		of the ploop disk and corresponding socket.
		"""

		# Create delta_receiver objects, one per active ploop delta
		self.__log_init_receiver(deltas)
		self.__delta_receivers = []
		for delta_path, delta_fd in deltas:
			self.__check_delta(delta_path)
			self.__delta_receivers.append(delta_receiver(delta_path, delta_fd))

	def start_receive(self):
		"""Start all delta receiver threads"""
		for receiver in self.__delta_receivers:
			receiver.start()

	def stop_receive(self):
		"""Join all delta receiver threads"""
		for receiver in self.__delta_receivers:
			receiver.join()

	def __log_init_receiver(self, deltas):
		logging.info("Initialize ploop receiver")
		for delta in deltas:
			logging.info("\t`- %s", delta[0])

	def __check_delta(self, delta_path):
		"""Check parent directory of delta exist"""

		delta_dir = os.path.dirname(delta_path)
		if not os.path.isdir(delta_dir):
			raise Exception("{0} directory missing".format(delta_dir))


class delta_receiver(threading.Thread):
	def __init__(self, delta_path, delta_fd):
		"""Initialize ploop single active delta receiver"""
		threading.Thread.__init__(self)
		self.__path = delta_path
		self.__fd = delta_fd

	def run(self):
		try:
			libploop.ploopcopy_receiver(self.__path, self.__fd)
		except Exception:
			logging.exception("Exception in %s delta receiver", self.__path)
