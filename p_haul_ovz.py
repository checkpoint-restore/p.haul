#
# OpenVZ containers hauler module
#

import os

name = "ovz"
vzpid_dir = "/var/lib/vzctl/vepid/"
vz_dir = "/vz"
vzpriv_dir = "%s/private" % vz_dir
vzroot_dir = "%s/root" % vz_dir

class p_haul_type:
	def __init__(self, id):
		self.ctid = id
		self.fs_mounted = False

	def name(self):
		return name

	def id(self):
		return self.ctid

	def root_task_pid(self):
		pf = open(os.path.join(vzpid_dir, self.ctid))
		pid = pf.read()
		return int(pid)

	def __ct_priv(self):
		return "%s/%s" % (vzpriv_dir, self.ctid)

	def __ct_root(self):
		return "%s/%s" % (vzroot_dir, self.ctid)

	def prepare_fs(self):
		nroot = self.__ct_root()
		print "Mounting CT root to %s" % nroot
		os.system("mount --bind %s %s" % (self.__ct_priv(), nroot))
		self.fs_mounted = True
		return nroot

	def unroll_fs(self):
		if self.fs_mounted:
			print "Unmounting CT root"
			os.system("umount %s" % self.__ct_root())
			self.fs_mounted = False
