#
# OpenVZ containers hauler module
#

import os
import shutil
import p_haul_cgroup

name = "ovz"
vzpid_dir = "/var/lib/vzctl/vepid/"
vz_dir = "/vz"
vzpriv_dir = "%s/private" % vz_dir
vzroot_dir = "%s/root" % vz_dir
vz_conf_dir = "/etc/vz/conf/"
vz_pidfiles = "/var/lib/vzctl/vepid/"
cg_image_name = "ovzcg.img"

class p_haul_type:
	def __init__(self, id):
		self.ctid = id
		self.fs_mounted = False
		self.veths = []

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

	def __ct_config(self):
		return "%s.conf" % self.ctid

	#
	# Meta-images for OVZ -- container config and info about CGroups
	#
	def get_meta_images(self, dir):
		cg_img = os.path.join(dir, cg_image_name)
		p_haul_cgroup.dump_hier(self.root_task_pid(), cg_img)
		cfg_name = self.__ct_config()
		return [ (os.path.join(vz_conf_dir, cfg_name), cfg_name), \
			 (cg_img, cg_image_name) ]

	def put_meta_images(self, dir):
		print "Putting config file into %s" % vz_conf_dir
		cfg_name = self.__ct_config()

		#
		# Copy config into /etc parsing it at the same time
		#

		ifd = open(os.path.join(dir, self.__ct_config()))
		ofd = open(os.path.join(vz_conf_dir, self.__ct_config()), "w")
		for line in ifd:
			ofd.write(line)

			if line.startswith("NETIF="):
				#
				# Parse and keep veth pairs, later we will
				# equip restore request with this data
				#
				v_in = None
				v_out = None
				vs = line.split("=", 1)[1].strip("\"")
				for parm in vs.split(","):
					pa = parm.split("=")
					if pa[0] == "ifname":
						v_in = pa[1]
					elif pa[0] == "host_ifname":
						v_out = pa[1]

					if v_in and v_out:
						self.veths.append((v_in, v_out))
						break
		ifd.close()
		ofd.close()

		# Keep this name, we'll need one in prepare_ct()
		self.cg_img = os.path.join(dir, cg_image_name)

	#
	# Create cgroup hierarchy and put root task into it
	# Hierarchy is unlimited, we will apply config limitations
	# in ->restored->__apply_cg_config later
	#
	def prepare_ct(self, pid):
		p_haul_cgroup.restore_hier(pid, self.cg_img)

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

	def __apply_cg_config(self):
		print "Applying CT configs"
		# FIXME -- implement
		pass

	def restored(self, pid):
		print "Writing pidfile"
		pidfile = open(os.path.join(vz_pidfiles, self.ctid), 'w')
		pidfile.write("%d" % pid)
		pidfile.close()

		self.__apply_cg_config()
