#
# OpenVZ containers hauler module
#

import os
import shutil
import p_haul_cgroup
import p_haul_netifapi as netif

name = "ovz"
vzpid_dir = "/var/lib/vzctl/vepid/"
vz_dir = "/vz"
vzpriv_dir = "%s/private" % vz_dir
vzroot_dir = "%s/root" % vz_dir
vz_conf_dir = "/etc/vz/conf/"
vz_pidfiles = "/var/lib/vzctl/vepid/"
cg_image_name = "ovzcg.img"

class p_haul_type:
	def __load_ct_config(self, dir):
		print "Loading config file from %s" % dir
		ifd = open(os.path.join(dir, self.__ct_config()))
		for line in ifd:
			self._cfg.append(line)

			if line.startswith("NETIF="):
				#
				# Parse and keep veth pairs, later we will
				# equip restore request with this data
				#
				v_in = None
				v_out = None
				v_bridge = None
				vs = line.strip().split("=", 1)[1].strip("\"")
				for parm in vs.split(","):
					pa = parm.split("=")
					if pa[0] == "ifname":
						v_in = pa[1]
					elif pa[0] == "host_ifname":
						v_out = pa[1]
					elif pa[0] == "bridge":
						v_bridge = pa[1]

				if v_in and v_out:
					print "\tCollect %s -> %s (%s) veth" % (v_in, v_out, v_bridge)
					self._veths.append((v_in, v_out, v_bridge))

		ifd.close()

	def __init__(self, id):
		self._ctid = id
		self._veths = []
		self._cfg = []

	def id(self):
		return (name, self._ctid)

	def init_src(self):
		self._fs_mounted = True
		self._bridged = True
		self.__load_ct_config(vz_conf_dir)

	def init_dst(self):
		self._fs_mounted = False
		self._bridged = False

	def root_task_pid(self):
		pf = open(os.path.join(vzpid_dir, self._ctid))
		pid = pf.read()
		return int(pid)

	def __ct_priv(self):
		return "%s/%s" % (vzpriv_dir, self._ctid)

	def __ct_root(self):
		return "%s/%s" % (vzroot_dir, self._ctid)

	def __ct_config(self):
		return "%s.conf" % self._ctid

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

		self.__load_ct_config(dir)
		ofd = open(os.path.join(vz_conf_dir, self.__ct_config()), "w")
		ofd.writelines(self._cfg)
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

	def mount(self):
		nroot = self.__ct_root()
		print "Mounting CT root to %s" % nroot
		os.system("mount --bind %s %s" % (self.__ct_priv(), nroot))
		self._fs_mounted = True
		return nroot

	def veths(self):
		return self._veths

	def __umount_root(self):
		print "Umounting CT root"
		os.system("umount %s" % self.__ct_root())
		self._fs_mounted = False

	def umount(self):
		if self._fs_mounted:
			self.__umount_root()

	def __apply_cg_config(self):
		print "Applying CT configs"
		# FIXME -- implement
		pass

	def restored(self, pid):
		print "Writing pidfile"
		pidfile = open(os.path.join(vz_pidfiles, self._ctid), 'w')
		pidfile.write("%d" % pid)
		pidfile.close()

		self.__apply_cg_config()

	def net_lock(self):
		for veth in self._veths:
			netif.ifdown(veth[1])

	def net_unlock(self):
		for veth in self._veths:
			netif.ifup(veth[1])
			if veth[2] and not self._bridged:
				netif.bridge_add(veth[1], veth[2])
