#
# LinuX Containers hauler module
#

import logging
import os
import shutil
from subprocess import PIPE
from subprocess import Popen
import util

import criu_cr
import fs_haul_shared

lxc_dir = "/var/lib/lxc/"
lxc_rootfs_dir = "/usr/lib64/lxc/rootfs"


class p_haul_type(object):
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
		logging.info("Loading config file from %s", self.__ct_config())

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
				veth = util.net_dev()
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
		logging.info("Applying CT configs")
		# FIXME -- implement
		pass

	def init_src(self):
		self._fs_mounted = True
		self._bridged = True
		self.__load_ct_config()

	def init_dst(self):
		self._fs_mounted = False
		self._bridged = False
		self.__load_ct_config()

	def set_options(self, opts):
		pass

	def adjust_criu_req(self, req):
		"""Add module-specific options to criu request"""
		pass

	def root_task_pid(self):
		pid = -1

		pd = Popen(["lxc-info", "-n", self._ctname], stdout=PIPE)
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
	# Meta-images for LXC -- container config
	#
	def get_meta_images(self, dir):
		cfg_name = self.__ct_config()
		return [(cfg_name, "config")]

	def put_meta_images(self, dir):
		logging.info("Putting config file into %s", lxc_dir)
		shutil.copy(os.path.join(dir, "config"), self.__ct_config())

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

	def prepare_ct(self, pid):
		pass

	def mount(self):
		nroot = self.__ct_root()
		logging.info("Mounting CT root to %s", nroot)
		if not os.access(nroot, os.F_OK):
			os.makedirs(nroot)
		os.system("mount --bind %s %s" % (self.__ct_rootfs(), nroot))
		self._fs_mounted = True
		return nroot

	def umount(self):
		pass

	def start(self):
		pass

	def stop(self, umount):
		pass

	def get_fs(self, fdfs=None):
		return fs_haul_shared.p_haul_fs()

	def get_fs_receiver(self, fdfs=None):
		return None

	def restored(self, pid):
		self.__apply_cg_config()

	def net_lock(self):
		for veth in self._veths:
			util.ifdown(veth.pair)

	def net_unlock(self):
		for veth in self._veths:
			util.ifup(veth.pair)
			if veth.link and not self._bridged:
				util.bridge_add(veth.pair, veth.link)

	def can_migrate_tcp(self):
		return True

	def veths(self):
		#
		# Caller wants to see list of tuples with [0] being name
		# in CT and [1] being name on host. Just return existing
		# tuples, the [2] with bridge name wouldn't hurt
		#
		return self._veths

	def dump_need_page_server(self):
		return True
