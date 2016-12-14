#
# images driver for migration (without FS transfer)
#

import logging
import os
import shutil
import tarfile
import tempfile
import threading
import time
import util

import criu_api

def_path = "/var/local/p.haul-fs/"


class opendir(object):
	def __init__(self, path):
		self._dirname = path
		self._dirfd = os.open(path, os.O_DIRECTORY)
		util.set_cloexec(self)

	def close(self):
		os.close(self._dirfd)
		os._dirname = None
		os._dirfd = -1

	def name(self):
		return self._dirname

	def fileno(self):
		return self._dirfd


class untar_thread(threading.Thread):
	def __init__(self, sk, tdir):
		threading.Thread.__init__(self)
		self.__sk = sk
		self.__dir = tdir

	def run(self):
		try:
			tf_fileobj = util.tarfile_fileobj_wrap(self.__sk)
			tf = tarfile.open(mode="r|", fileobj=tf_fileobj)
			tf.extractall(self.__dir)
			tf.close()
			tf_fileobj.discard_unread_input()
		except Exception:
			logging.exception("Exception in untar_thread")


class img_tar(object):
	def __init__(self, sk, dirname):
		tf_fileobj = util.tarfile_fileobj_wrap(sk)
		self.__tf = tarfile.open(mode="w|", fileobj=tf_fileobj)
		self.__dir = dirname

	def add(self, img, path=None):
		if not path:
			path = os.path.join(self.__dir, img)

		self.__tf.add(path, img)

	def close(self):
		self.__tf.close()


class phaul_images(object):
	WDIR = 1
	IMGDIR = 2

	def __init__(self, typ):
		self.current_iter = 0
		self.sync_time = 0.0
		self._typ = typ
		self._keep_on_close = False
		self._wdir = None
		self._current_dir = None

	def save_images(self):
		logging.info("Keeping images")
		self._keep_on_close = True

	def set_options(self, opts):
		self._keep_on_close = opts["keep_images"]

		suf = time.strftime("-%y.%m.%d-%H.%M", time.localtime())
		util.makedirs(opts["img_path"])
		wdir = tempfile.mkdtemp(suf, "%s-" % self._typ, opts["img_path"])
		self._wdir = opendir(wdir)
		self._img_path = os.path.join(self._wdir.name(), "img")
		os.mkdir(self._img_path)

	def close(self):
		if not self._wdir:
			return

		self._wdir.close()
		if self._current_dir:
			self._current_dir.close()

		if not self._keep_on_close:
			logging.info("Removing images")
			shutil.rmtree(self._wdir.name())
		else:
			logging.info("Images are kept in %s", self._wdir.name())
		pass

	def img_sync_time(self):
		return self.sync_time

	def new_image_dir(self):
		if self._current_dir:
			self._current_dir.close()
		self.current_iter += 1
		img_dir = "%s/%d" % (self._img_path, self.current_iter)
		logging.info("\tMaking directory %s", img_dir)
		os.mkdir(img_dir)
		self._current_dir = opendir(img_dir)

	def image_dir_fd(self):
		return self._current_dir.fileno()

	def work_dir_fd(self):
		return self._wdir.fileno()

	def image_dir(self):
		return self._current_dir.name()

	def work_dir(self):
		return self._wdir.name()

	def prev_image_dir(self):
		if self.current_iter == 1:
			return None
		else:
			return "../%d" % (self.current_iter - 1)

	# Images transfer
	# Are there better ways for doing this?

	def sync_imgs_to_target(self, target_host, htype, sk):
		# Pre-dump doesn't generate any images (yet?)
		# so copy only those from the top dir
		logging.info("Sending images to target")

		start = time.time()
		cdir = self.image_dir()

		target_host.start_accept_images(phaul_images.IMGDIR)
		tf = img_tar(sk, cdir)

		logging.info("\tPack")
		for img in filter(lambda x: x.endswith(".img"), os.listdir(cdir)):
			tf.add(img)

		logging.info("\tAdd htype images")
		for himg in htype.get_meta_images(cdir):
			tf.add(himg[1], himg[0])

		tf.close()
		target_host.stop_accept_images()

		self.sync_time = time.time() - start

	def send_cpuinfo(self, target_host, sk):
		target_host.start_accept_images(phaul_images.WDIR)
		tf = img_tar(sk, self.work_dir())
		tf.add(criu_api.cpuinfo_img_name)
		tf.close()
		target_host.stop_accept_images()

	def start_accept_images(self, dir_id, sk):
		if dir_id == phaul_images.WDIR:
			dirname = self.work_dir()
		else:
			dirname = self.image_dir()

		self.__acc_tar = untar_thread(sk, dirname)
		self.__acc_tar.start()
		logging.info("Started images server")

	def stop_accept_images(self):
		logging.info("Waiting for images to unpack")
		self.__acc_tar.join()
