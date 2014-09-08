#
# OpenVZ containers hauler module
#

import os
import shutil
import p_haul_cgroup
import p_haul_netifapi as netif
import util
import fs_haul_shared
import fs_haul_subtree

name = "ovz"
vzpid_dir = "/var/lib/vzctl/vepid/"
vz_dir = "/vz"
vzpriv_dir = "%s/private" % vz_dir
vzroot_dir = "%s/root" % vz_dir
vz_conf_dir = "/etc/vz/conf/"
vz_pidfiles = "/var/lib/vzctl/vepid/"
cg_image_name = "ovzcg.img"

class p_haul_type:
	def __init__(self, ctid):
		self._ctid = ctid
		#
		# This list would contain (v_in, v_out, v_br) tuples where
		# v_in is the name of veth device in CT
		# v_out is its peer on the host
		# v_bridge is the bridge to which thie veth is attached
		#
		self._veths = []
		self._cfg = []

	def __load_ct_config(self, path):
		print "Loading config file from %s" % path
		ifd = open(os.path.join(path, self.__ct_config()))
		for line in ifd:
			self._cfg.append(line)

			if line.startswith("NETIF="):
				#
				# Parse and keep veth pairs, later we will
				# equip restore request with this data and
				# will use it while (un)locking the network
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
					veth = util.net_dev()
					veth.name = v_in
					veth.pair = v_out
					veth.link = v_bridge
					self._veths.append(veth)

		ifd.close()

	def __apply_cg_config(self):
		print "Applying CT configs"
		# FIXME -- implement
		pass

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
	def get_meta_images(self, path):
		cg_img = os.path.join(path, cg_image_name)
		p_haul_cgroup.dump_hier(self.root_task_pid(), cg_img)
		cfg_name = self.__ct_config()
		return [ (os.path.join(vz_conf_dir, cfg_name), cfg_name), \
			 (cg_img, cg_image_name) ]

	def put_meta_images(self, path):
		print "Putting config file into %s" % vz_conf_dir

		self.__load_ct_config(path)
		ofd = open(os.path.join(vz_conf_dir, self.__ct_config()), "w")
		ofd.writelines(self._cfg)
		ofd.close()

		# Keep this name, we'll need one in prepare_ct()
		self.cg_img = os.path.join(path, cg_image_name)

	#
	# Create cgroup hierarchy and put root task into it
	# Hierarchy is unlimited, we will apply config limitations
	# in ->restored->__apply_cg_config later
	#
	def prepare_ct(self, pid):
		p_haul_cgroup.restore_hier(pid, self.cg_img)

	def __umount_root(self):
		print "Umounting CT root"
		os.system("umount %s" % self.__ct_root())
		self._fs_mounted = False

	def mount(self):
		nroot = self.__ct_root()
		print "Mounting CT root to %s" % nroot
		if not os.access(nroot, os.F_OK):
			os.makedirs(nroot)
		os.system("mount --bind %s %s" % (self.__ct_priv(), nroot))
		self._fs_mounted = True
		return nroot

	def umount(self):
		if self._fs_mounted:
			self.__umount_root()

	def get_fs(self):
		rootfs = fsapi.path_to_fs(self.__ct_priv())
		if not rootfs:
			print "CT is on unknown FS"
			return None

		print "CT is on %s" % rootfs

		if rootfs == "nfs":
			return fs_haul_shared.p_haul_fs()
		if rootfs == "ext3" or rootfs == "ext4":
			return fs_haul_subtree.p_haul_fs(self.__ct_priv())

		print "Unknown CT FS"
		return None

	def restored(self, pid):
		print "Writing pidfile"
		pidfile = open(os.path.join(vz_pidfiles, self._ctid), 'w')
		pidfile.write("%d" % pid)
		pidfile.close()

		self.__apply_cg_config()

	def net_lock(self):
		for veth in self._veths:
			netif.ifdown(veth.pair)

	def net_unlock(self):
		for veth in self._veths:
			netif.ifup(veth.pair)
			if veth.link and not self._bridged:
				netif.bridge_add(veth.pair, veth.link)

	def can_migrate_tcp(self):
		return True

	def veths(self):
		#
		# Caller wants to see list of tuples with [0] being name
		# in CT and [1] being name on host. Just return existing
		# tuples, the [2] with bridge name wouldn't hurt
		#
		return self._veths

