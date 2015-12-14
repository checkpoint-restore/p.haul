#
# ploop disk hauler
#

import os
import logging
import threading
import libploop


DDXML_FILENAME = "DiskDescriptor.xml"


class p_haul_fs:
	def __init__(self, ddxml_path, fs_sk):
		"""Initialize ploop disk hauler

		Initialize ploop disk hauler with specified path to DiskDescriptor.xml
		file and socket.
		"""

		logging.info("Initilized ploop hauler (%s)", ddxml_path)
		self.__ploopcopy = libploop.ploopcopy(ddxml_path, fs_sk.fileno())

	def set_options(self, opts):
		pass

	def set_work_dir(self, wdir):
		pass

	def start_migration(self):
		self.__ploopcopy.copy_start()

	def next_iteration(self):
		self.__ploopcopy.copy_next_iteration()

	def stop_migration(self):
		self.__ploopcopy.copy_stop()

	def persistent_inodes(self):
		"""Inode numbers do not change during ploop disk migration"""
		return True

	def __log_init_hauler(self, deltas):
		logging.info("Initialize ploop hauler")
		for delta in deltas:
			logging.info("\t`- %s", delta[0])

	def __get_ddxml_path(self, delta_path):
		"""Get path to disk descriptor file by path to disk delta"""
		return os.path.join(os.path.dirname(delta_path), DDXML_FILENAME)

	def __check_ddxml(self, ddxml_path):
		"""Check disk descriptor file exist"""
		if not os.path.isfile(ddxml_path):
			raise Exception("{0} file missing".format(ddxml_path))


class p_haul_fs_receiver:
	def __init__(self, fname_path, fs_sk):
		"""Initialize ploop disk receiver

		Initialize ploop disk receiver with specified path to root.hds file
		and socket.
		"""

		self.__delta_receiver = delta_receiver(fname_path, fs_sk)

	def start_receive(self):
		self.__delta_receiver.start()

	def stop_receive(self):
		self.__delta_receiver.join()

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
