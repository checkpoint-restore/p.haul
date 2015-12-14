#
# Virtuozzo containers hauler module
#

import os
import subprocess
import shlex
import logging
import criu_cr
import util
import fs_haul_ploop
import pycriu.rpc


vz_global_conf = "/etc/vz/vz.conf"
vz_conf_dir = "/etc/vz/conf/"
vzctl_bin = "vzctl"


class p_haul_type:
	def __init__(self, ctid):
		self._ctid = ctid
		self._ct_priv = ""
		self._ct_root = ""
		#
		# This list would contain (v_in, v_out, v_br) tuples where
		# v_in is the name of veth device in CT
		# v_out is its peer on the host
		# v_bridge is the bridge to which thie veth is attached
		#
		self._veths = []

	def __load_ct_config(self, path):
		logging.info("Loading config file from %s", path)

		# Read container config
		with open(self.__ct_config_path(path)) as ifd:
			config = _parse_vz_config(ifd.read())

		# Read global config
		with open(vz_global_conf) as ifd:
			global_config = _parse_vz_config(ifd.read())

		# Extract veth pairs, later we will equip restore request with this
		# data and will use it while (un)locking the network
		if "NETIF" in config:
			v_in, v_out, v_bridge = None, None, None
			for parm in config["NETIF"].split(","):
				pa = parm.split("=")
				if pa[0] == "ifname":
					v_in = pa[1]
				elif pa[0] == "host_ifname":
					v_out = pa[1]
				elif pa[0] == "bridge":
					v_bridge = pa[1]
			if v_in and v_out:
				logging.info("\tCollect %s -> %s (%s) veth", v_in, v_out, v_bridge)
				self._veths.append(util.net_dev(v_in, v_out, v_bridge))

		# Extract private path from config
		if "VE_PRIVATE" in config:
			self._ct_priv = _expand_veid_var(config["VE_PRIVATE"], self._ctid)
		else:
			self._ct_priv = _expand_veid_var(global_config["VE_PRIVATE"],
				self._ctid)

		# Extract root path from config
		if "VE_ROOT" in config:
			self._ct_root = _expand_veid_var(config["VE_ROOT"], self._ctid)
		else:
			self._ct_root = _expand_veid_var(global_config["VE_ROOT"],
				self._ctid)

	def __load_ct_config_dst(self, path):
		if not os.path.isfile(self.__ct_config_path(path)):
			raise Exception("CT config missing on destination")
		self.__load_ct_config(path)

	def __ct_config_path(self, conf_dir):
		return os.path.join(conf_dir, "{0}.conf".format(self._ctid))

	def __cg_set_veid(self):
		"""Initialize veid in ve.veid for ve cgroup"""

		veid_path = "/sys/fs/cgroup/ve/{0}/ve.veid".format(self._ctid)
		with open(veid_path, "w") as f:
			if self._ctid.isdigit():
				veid = self._ctid
			else:
				veid = str(int(self._ctid.partition("-")[0], 16))
			f.write(veid)

	def init_src(self):
		self._fs_mounted = True
		self._bridged = True
		self.__load_ct_config(vz_conf_dir)

	def init_dst(self):
		self._fs_mounted = False
		self._bridged = False
		self.__load_ct_config_dst(vz_conf_dir)

	def set_options(self, opts):
		pass

	def adjust_criu_req(self, req):
		"""Add module-specific options to criu request"""
		if req.type == pycriu.rpc.DUMP or req.type == pycriu.rpc.RESTORE:
			# Restore cgroups configuration
			req.opts.manage_cgroups = True
			# Automatically resolve external mounts
			req.opts.auto_ext_mnt = True
			req.opts.ext_sharing = True
			req.opts.ext_masters = True

	def root_task_pid(self):
		# Expect first line of tasks file contain root pid of CT
		path = "/sys/fs/cgroup/memory/{0}/tasks".format(self._ctid)
		with open(path) as tasks:
			pid = tasks.readline()
			return int(pid)

	def get_meta_images(self, path):
		return []

	def put_meta_images(self, path):
		pass

	def __setup_restore_extra_args(self, path, img, connection):
		"""Create temporary file with extra arguments for criu restore"""
		extra_args = [
			"VE_WORK_DIR={0}\n".format(img.work_dir()),
			"VE_RESTORE_LOG_PATH={0}\n".format(
				connection.get_log_name(pycriu.rpc.RESTORE))]
		with open(path, "w") as f:
			f.writelines(extra_args)

	def __remove_restore_extra_args(self, path):
		"""Remove temporary file with extra arguments for criu restore"""
		if os.path.isfile(path):
			os.remove(path)

	def final_dump(self, pid, img, ccon, fs):
		criu_cr.criu_dump(self, pid, img, ccon, fs)

	def final_restore(self, img, connection):
		"""Perform Virtuozzo-specific final restore"""
		try:
			# Setup restore extra arguments
			args_path = os.path.join(img.image_dir(), "restore-extra-args")
			self.__setup_restore_extra_args(args_path, img, connection)
			# Run vzctl restore
			logging.info("Starting vzctl restore")
			proc = subprocess.Popen([vzctl_bin, "--skiplock", "restore",
				self._ctid, "--dumpfile", img.image_dir()],
				stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
			proc_output = proc.communicate()[0]
			logging.info(proc_output)
			if proc.returncode != 0:
				raise Exception("Restore failed ({0})".format(proc.returncode))
		finally:
			# Remove restore extra arguments
			self.__remove_restore_extra_args(args_path)

	def prepare_ct(self, pid):
		"""Create cgroup hierarchy and put root task into it."""
		self.__cg_set_veid()

	def mount(self):
		logging.info("Mounting CT root to %s", self._ct_root)
		logging.info("Starting vzctl mount")
		proc = subprocess.Popen(
			[vzctl_bin, "--skiplock", "mount", self._ctid],
			stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		proc_output = proc.communicate()[0]
		logging.info(proc_output)
		self._fs_mounted = True
		return self._ct_root

	def umount(self):
		if self._fs_mounted:
			logging.info("Umounting CT root")
			logging.info("Starting vzctl umount")
			proc = subprocess.Popen(
				[vzctl_bin, "--skiplock", "umount", self._ctid],
				stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
			proc_output = proc.communicate()[0]
			logging.info(proc_output)
			self._fs_mounted = False

	def get_fs(self, fs_sk=None):
		deltas = [(os.path.join(self._ct_priv, "root.hdd", "root.hds"), fs_sk)]
		return fs_haul_ploop.p_haul_fs(deltas)

	def get_fs_receiver(self, fs_sk=None):
		deltas = [(os.path.join(self._ct_priv, "root.hdd", "root.hds"), fs_sk)]
		return fs_haul_ploop.p_haul_fs_receiver(deltas)

	def restored(self, pid):
		pass

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

	def can_pre_dump(self):
		return True

	def dump_need_page_server(self):
		return True


def add_hauler_args(parser):
	"""Add Virtuozzo specific command line arguments"""
	parser.add_argument("--vz-dst-ctid", help="ctid at destination")


def _parse_vz_config(body):
	"""Parse shell-like virtuozzo config file"""

	config_values = dict()
	for token in shlex.split(body, comments=True):
		name, sep, value = token.partition("=")
		config_values[name] = value
	return config_values


def _expand_veid_var(value, ctid):
	"""Replace shell-like VEID variable with actual container id"""
	return value.replace("$VEID", ctid).replace("${VEID}", ctid)
