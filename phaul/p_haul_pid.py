#
# Individual process hauler
#

import logging

import criu_cr
import fs_haul_shared


class p_haul_type(object):
	def __init__(self, id):
		self.pid = int(id)
		self._pidfile = None

	#
	# Initialize itself for source node or destination one
	#
	def init_src(self):
		pass

	def init_dst(self):
		pass

	def set_options(self, opts):
		self._pidfile = opts["dst_rpid"]
		self._fs_root = opts["pid_root"]

	def adjust_criu_req(self, req):
		"""Add module-specific options to criu request"""
		pass

	# Report the pid of the root task of what we're
	# goung to migrate
	def root_task_pid(self):
		return self.pid

	# Prepare filesystem before restoring. Retrun
	# the new root, if required. 'None' will mean
	# that things will get restored in the current
	# mount namespace and w/o chroot
	def mount(self):
		return self._fs_root

	# Remove any specific FS setup
	def umount(self):
		pass

	def start(self):
		pass

	def stop(self, umount):
		pass

	# Get driver for FS migration
	def get_fs(self, fdfs=None):
		return fs_haul_shared.p_haul_fs()

	def get_fs_receiver(self, fdfs=None):
		return None

	# Get list of files which should be copied to
	# the destination node. The dir argument is where
	# temporary stuff can be put
	def get_meta_images(self, dir):
		return []

	# Take your files from dir and put in whatever
	# places are appropriate. Paths (relative) are
	# preserved.
	def put_meta_images(self, dir):
		pass

	def final_dump(self, pid, img, ccon, fs):
		criu_cr.criu_dump(self, pid, img, ccon, fs)

	def migration_complete(self, fs, target_host):
		pass

	def migration_fail(self, fs):
		pass

	def target_cleanup(self, src_data):
		pass

	def final_restore(self, img, connection):
		criu_cr.criu_restore(self, img, connection)

	# Things are started to get restored, only the
	# first task (with pid @pid) is created.
	def prepare_ct(self, pid):
		pass

	# Restoring done, the new top task has pid pid
	def restored(self, pid):
		if self._pidfile:
			logging.info("Writing rst pidfile")
			open(self._pidfile, "w").writelines(["%d" % pid])

	#
	# Lock and unlock networking
	#
	def net_lock(self):
		pass

	def net_unlock(self):
		pass

	def can_migrate_tcp(self):
		return False

	# Get list of veth pairs if any
	def veths(self):
		return []

	def can_pre_dump(self):
		return True

	def dump_need_page_server(self):
		return True
