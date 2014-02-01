#
# OpenVZ containers hauler module
#

import os
import shutil

name = "ovz"
vzpid_dir = "/var/lib/vzctl/vepid/"
vz_dir = "/vz"
vzpriv_dir = "%s/private" % vz_dir
vzroot_dir = "%s/root" % vz_dir
vz_conf_dir = "/etc/vz/conf/"
vz_pidfiles = "/var/lib/vzctl/vepid/"

class p_haul_type:
	def __init__(self, id):
		self.ctid = id
		self.fs_mounted = False

	def id(self):
		return (name, self.ctid)

	def root_task_pid(self):
		pf = open(os.path.join(vzpid_dir, self.ctid))
		pid = pf.read()
		return int(pid)

	def __ct_priv(self):
		return "%s/%s" % (vzpriv_dir, self.ctid)

	def __ct_root(self):
		return "%s/%s" % (vzroot_dir, self.ctid)

	def get_meta_images(self):
		return [ os.path.join(vz_conf_dir, "%s.conf" % self.ctid) ]

	def put_meta_images(self, dir):
		print "Putting config file into %s" % vz_conf_dir
		shutil.copy("%s/%s/%s.conf" % (dir, vz_conf_dir, self.ctid), vz_conf_dir)

	def prepare_fs(self):
		nroot = self.__ct_root()
		print "Mounting CT root to %s" % nroot
		os.system("mount --bind %s %s" % (self.__ct_priv(), nroot))
		self.fs_mounted = True
		return nroot

	def __umount_root(self):
		print "Umounting CT root"
		os.system("umount %s" % self.__ct_root())
		self.fs_mounted = False

	def unroll_fs(self):
		if self.fs_mounted:
			self.__umount_root()

	def clean_migrated(self):
		self.__umount_root()

	def restored(self, pid):
		print "Writing pidfile"
		pidfile = open(os.path.join(vz_pidfiles, self.ctid), 'w')
		pidfile.write("%d" % pid)
		pidfile.close()
