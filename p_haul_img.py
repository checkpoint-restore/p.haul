#
# images driver for migration (without FS transfer)
#

import os
import tempfile
import rpyc
import tarfile
import time
import shutil
import time
import threading

img_path = "/var/local/p.haul-fs/"
img_tarfile = "images.tar"
xfer_size = 64 * 1024

def copy_file(s, d):
	while True:
		chunk = s.read(xfer_size)
		if not chunk:
			break
		d.write(chunk)

class phaul_images:
	def __init__(self):
		self.current_iter = 0
		self.current_dir = None
		prefix = time.strftime("%y.%m.%d-%H.%M-", time.localtime())
		self.wdir = tempfile.mkdtemp("", prefix, img_path)
		self.img_path = os.path.join(self.wdir, "img")
		os.mkdir(self.img_path)
		self.sync_time = 0.0

	def close(self, keep_images):
		if not keep_images:
			print "Removing images"
			shutil.rmtree(self.wdir)
		else:
			print "Images are kept in %s" % self.wdir
		pass

	def img_sync_time(self):
		return self.sync_time

	def new_image_dir(self):
		self.current_iter += 1
		img_dir = "%s/%d" % (self.img_path, self.current_iter)
		print "\tMaking directory %s" % img_dir
		self.current_dir = img_dir
		os.mkdir(img_dir)

	def image_dir_fd(self):
		return os.open(self.current_dir, os.O_DIRECTORY)

	def work_dir_fd(self):
		return os.open(self.wdir, os.O_DIRECTORY)

	def image_dir(self):
		return self.current_dir

	def work_dir(self):
		return self.wdir

	def prev_image_dir(self):
		if self.current_iter == 1:
			return None
		else:
			return "../%d" % (self.current_iter - 1)

	# Images transfer
	# Are there better ways for doing this?

	def sync_imgs_to_target(self, th, htype, sock):
		# Pre-dump doesn't generate any images (yet?)
		# so copy only those from the top dir
		print "Sending images to target"

		start = time.time()

		th.start_accept_images()

		print "\tPack"
		tf_name = os.path.join(self.current_dir, img_tarfile)
		tf = tarfile.open(mode = "w|", fileobj = sock.tofile())
		for img in os.listdir(self.current_dir):
			if img.endswith(".img"):
				tf.add(os.path.join(self.current_dir, img), img)

		print "\tAdd htype images"
		for himg in htype.get_meta_images(self.current_dir):
			tf.add(himg[0], himg[1])

		tf.close()

		th.stop_accept_images()

		self.sync_time = time.time() - start

class untar_thread(threading.Thread):
	def __init__(self, sk, tdir):
		threading.Thread.__init__(self)
		self.__sk = sk
		self.__dir = tdir

	def run(self):
		tf = tarfile.open(mode = "r|", fileobj = self.__sk.tofile())
		tf.extractall(self.__dir)
		tf.close()
