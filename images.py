#
# images driver for migration (without FS transfer)
#

import os
import tempfile
import tarfile
import time
import shutil
import time
import threading
import util
import criu_api

def_path = "/var/local/p.haul-fs/"

class opendir:
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

class phaul_images:
	def __init__(self, typ):
		self.current_iter = 0
		self.sync_time = 0.0
		self._typ = typ
		self._keep_on_close = False
		self._wdir = None
		self._current_dir = None

	def save_images(self):
		print "Keeping images"
		self._keep_on_close = True

	def set_options(self, opts):
		self._keep_on_close = opts["keep_images"]

		suf = time.strftime("-%y.%m.%d-%H.%M", time.localtime())
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
			print "Removing images"
			shutil.rmtree(self._wdir.name())
		else:
			print "Images are kept in %s" % self._wdir.name()
		pass

	def img_sync_time(self):
		return self.sync_time

	def new_image_dir(self):
		if self._current_dir:
			self._current_dir.close()
		self.current_iter += 1
		img_dir = "%s/%d" % (self._img_path, self.current_iter)
		print "\tMaking directory %s" % img_dir
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

	def __tar_to_sock(self, sock):
		return tarfile.open(mode = "w|", fileobj = sock.makefile())


	def sync_imgs_to_target(self, th, htype, sock):
		# Pre-dump doesn't generate any images (yet?)
		# so copy only those from the top dir
		print "Sending images to target"

		start = time.time()

		th.start_accept_images()
		tf = self.__tar_to_sock(sock)

		print "\tPack"
		cdir = self._current_dir.name()
		for img in filter(lambda x: x.endswith(".img"), os.listdir(cdir)):
			tf.add(os.path.join(cdir, img), img)

		print "\tAdd htype images"
		for himg in htype.get_meta_images(cdir):
			tf.add(himg[0], himg[1])

		tf.close()

		th.stop_accept_images()

		self.sync_time = time.time() - start

	def send_cpuinfo(self, th, sock):
		th.start_accept_wdir()
		tf = self.__tar_to_sock(sock)
		img = criu_api.cpuinfo_img_name
		cdir = self._wdir.name()
		tf.add(os.path.join(cdir, img), img)
		tf.close()
		th.stop_accept_images()

class untar_thread(threading.Thread):
	def __init__(self, sk, tdir):
		threading.Thread.__init__(self)
		self.__sk = sk
		self.__dir = tdir

	def run(self):
		tf = tarfile.open(mode = "r|", fileobj = self.__sk.makefile())
		tf.extractall(self.__dir)
		tf.close()
