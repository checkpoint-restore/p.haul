#
# LinuX Containers hauler module
#

import os
import shutil
import p_haul_cgroup
import p_haul_netifapi as netif
import p_haul_fsapi as fsapi
import p_haul_netapi as netapi
import fs_haul_shared
import fs_haul_subtree
from subprocess import Popen, PIPE

name = "lxc"
lxc_dir = "/var/lib/lxc/"
lxc_rootfs_dir = "/usr/lib64/lxc/rootfs"
cg_image_name = "lxccg.img"

class p_haul_type:
	def __init__(self, name):
		self._ctname = name
		#
		# This list would contain (v_in, v_out, v_br) tuples where
		# v_in is the name of veth device in CT
		# v_out is its peer on the host
		# v_bridge is the bridge to which thie veth is attached
		#
		self._veths = []
		self._cfg = {}

	def __load_ct_config(self):
		print "Loading config file from %s" % self.__ct_config()

		self._cfg = {}
		self._veths = []

		veth = None

		ifd = open(self.__ct_config())
		for line in ifd:
			if not ("=" in line):
				continue
			k, v = map(lambda a: a.strip(), line.split("=", 1))
			self._cfg[k] = v

			if k == "lxc.network.type":
				if v != "veth":
					raise Exception("Unsupported network device type: %s", v)
				if veth:
					self._veths.append(veth)
				veth = netapi.net_dev()
			elif k == "lxc.network.link":
				veth.link = v
			elif k == "lxc.network.name":
				veth.name = v
			elif k == "lxc.network.veth.pair":
				veth.pair = v
		if veth:
			self._veths.append(veth)
		ifd.close()

	def __apply_cg_config(self):
		print "Applying CT configs"
		# FIXME -- implement
		pass

	def id(self):
		return (name, self._ctname)

	def init_src(self):
		self._fs_mounted = True
		self._bridged = True
		self.__load_ct_config()

	def init_dst(self):
		self._fs_mounted = False
		self._bridged = False
		self.__load_ct_config()

	def root_task_pid(self):
		pid = -1;

		pd = Popen(["lxc-info", "-n", self._ctname], stdout = PIPE)
		for l in pd.stdout:
			if l.startswith("PID:"):
				pid = int(l.split(":")[1])
		status = pd.wait()
		if status:
			raise Exception("lxc info -n %s failed: %d" %
						(self._ctname, status))
		if pid == -1:
			raise Exception("CT isn't running")
		return pid

	def __ct_rootfs(self):
		return self._cfg['lxc.rootfs']

	def __ct_root(self):
		return os.path.join(lxc_rootfs_dir, self._ctname)

	def __ct_config(self):
		return os.path.join(lxc_dir, self._ctname, "config")

	#
	# Meta-images for LXC -- container config and info about CGroups
	#
	def get_meta_images(self, dir):
		cg_img = os.path.join(dir, cg_image_name)
		p_haul_cgroup.dump_hier(self.root_task_pid(), cg_img)
		cfg_name = self.__ct_config()
		return [ (cfg_name, "config"),
			 (cg_img, cg_image_name) ]

	def put_meta_images(self, dir):
		print "Putting config file into %s" % lxc_dir

		shutil.copy(os.path.join(dir, "config"), self.__ct_config())

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
		if not os.access(nroot, os.F_OK):
			os.makedirs(nroot)
		os.system("mount --bind %s %s" % (self.__ct_rootfs(), nroot))
		self._fs_mounted = True
		return nroot

	def get_fs(self):
		return fs_haul_shared.p_haul_fs()

	def restored(self, pid):
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

	def umount(self):
		pass

	def veths(self):
		#
		# Caller wants to see list of tuples with [0] being name
		# in CT and [1] being name on host. Just return existing
		# tuples, the [2] with bridge name wouldn't hurt
		#
		return self._veths
