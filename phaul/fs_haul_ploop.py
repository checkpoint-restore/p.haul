#
# ploop disk hauler
#

import os
import logging
import threading
import libploop
import mstats


DDXML_FILENAME = "DiskDescriptor.xml"


def get_ddxml_path(path):
	"""Get path to disk descriptor file by path to disk delta or directory"""
	p = path if os.path.isdir(path) else os.path.dirname(path)
	return os.path.join(p, DDXML_FILENAME)


class p_haul_fs:
	def __init__(self, deltas):
		"""Initialize ploop disks hauler

		For each disk create libploop.ploopcopy object using path to disk
		descriptor file and corresponding socket.
		"""

		# Create libploop.ploopcopy objects, one per active ploop delta
		self.__log_init_hauler(deltas)
		self.__ploop_copies = []
		for delta_path, delta_fd in deltas:
			ddxml_path = get_ddxml_path(delta_path)
			self.__check_ddxml(ddxml_path)
			self.__ploop_copies.append(
				libploop.ploopcopy(ddxml_path, delta_fd))

	def set_options(self, opts):
		pass

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
		return mstats.fs_iter_stats(total_xferred)

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


class p_haul_fs_receiver:
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
		"""Check delta file don't exist and parent directory exist"""

		delta_dir = os.path.dirname(delta_path)
		if not os.path.isdir(delta_dir):
			raise Exception("{0} directory missing".format(delta_dir))

		if os.path.isfile(delta_path):
			raise Exception("{0} already exist".format(delta_path))


class delta_receiver(threading.Thread):
	def __init__(self, delta_path, delta_fd):
		"""Initialize ploop single active delta receiver"""
		threading.Thread.__init__(self)
		self.__path = delta_path
		self.__fd = delta_fd

	def run(self):
		try:
			libploop.ploopcopy_receiver(self.__path, self.__fd)
		except:
			logging.exception("Exception in %s delta receiver", self.__path)
