#
# Virtuozzo containers hauler module
#

import os
import subprocess
import shlex
import logging
import criu_cr
import criu_api
import util
import fs_haul_ploop
import pycriu.rpc


vz_global_conf = "/etc/vz/vz.conf"
vz_conf_dir = "/etc/vz/conf/"
vzctl_bin = "vzctl"
cgget_bin = "cgget"
cgexec_bin = "cgexec"


vz_cgroup_mount_map = {
	"/sys/fs/cgroup/cpu,cpuacct": "cpu",
	"/sys/fs/cgroup/cpuset": "cpuset",
	"/sys/fs/cgroup/net_cls": "net_cls",
	"/sys/fs/cgroup/memory": "memory",
	"/sys/fs/cgroup/devices": "devices",
	"/sys/fs/cgroup/blkio": "blkio",
	"/sys/fs/cgroup/freezer": "freezer",
	"/sys/fs/cgroup/beancounter": "beancounter",
	"/sys/fs/cgroup/ve": "ve",
	"/sys/fs/cgroup/perf_event": "perf_event",
	"/sys/fs/cgroup/hugetlb": "hugetlb",
	"/sys/fs/cgroup/systemd": "systemd",
}


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
		self.__verbose = criu_api.def_verb

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
		self.__verbose = opts["verbose"]

	def adjust_criu_req(self, req):
		"""Add module-specific options to criu request"""

		# Specify dump specific options
		if req.type == pycriu.rpc.DUMP:

			# Specify root fs
			req.opts.root = self._ct_root

			# Restore cgroups configuration
			req.opts.manage_cgroups = True

			# Setup mapping for external Virtuozzo specific cgroup mounts
			for key, value in vz_cgroup_mount_map.items():
				req.opts.ext_mnt.add(key=key, val=value)

			# Increase ghost-limit up to 50Mb
			req.opts.ghost_limit = 50 << 20

		# Specify freezer cgroup for both predump and dump requests
		if req.type == pycriu.rpc.PRE_DUMP or req.type == pycriu.rpc.DUMP:
			req.opts.freeze_cgroup = \
				"/sys/fs/cgroup/freezer/{0}/".format(self._ctid)

	def root_task_pid(self):
		path = "/var/run/ve/{0}.init.pid".format(self._ctid)
		with open(path) as pidfile:
			pid = pidfile.read()
			return int(pid)

	def get_meta_images(self, path):
		return []

	def put_meta_images(self, path):
		pass

	def final_dump(self, pid, img, ccon, fs):
		"""Perform Virtuozzo-specific final dump"""
		self.__pre_final_dump(img)
		criu_cr.criu_dump(self, pid, img, ccon, fs)
		self.__post_final_dump(img)

	def __pre_final_dump(self, img):
		"""Create extra images before final dump"""
		extra_images = (
			("vz_clock_bootbased.img", "ve.clock_bootbased"),
			("vz_clock_monotonic.img", "ve.clock_monotonic"),
			("vz_iptables_mask.img", "ve.iptables_mask"),
			("vz_os_release.img", "ve.os_release"),
			("vz_features.img", "ve.features"),
			("vz_aio_max_nr.img", "ve.aio_max_nr"))
		for image_name, var_name in extra_images:
			self.__create_cgget_extra_image(img, image_name, var_name)

	def __post_final_dump(self, img):
		"""Create extra images after final dump"""
		extra_images = (
			("vz_core_pattern.img", ["cat", "/proc/sys/kernel/core_pattern"]),)
		for image_name, exec_args in extra_images:
			self.__create_cgexec_extra_image(img, image_name, exec_args)

	def __create_cgget_extra_image(self, img, image_name, var_name):
		"""Create extra image using cgget output"""
		proc = subprocess.Popen(
			[cgget_bin, "-n", "-v", "-r", var_name, self._ctid],
			stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		image_data = proc.communicate()[0]
		if proc.returncode == 0:
			self.__create_extra_image(img, image_name, image_data)
		else:
			logging.warning("cgget failed to create %s", image_name)

	def __create_cgexec_extra_image(self, img, image_name, exec_args):
		"""Create extra image using cgexec output"""
		proc = subprocess.Popen(
			[cgexec_bin, "-g", "ve:{0}".format(self._ctid)] + exec_args,
			stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		image_data = proc.communicate()[0]
		if proc.returncode == 0:
			self.__create_extra_image(img, image_name, image_data)
		else:
			logging.warning("cgexec failed to create %s", image_name)

	def __create_extra_image(self, img, image_name, image_data):
		image_path = os.path.join(img.image_dir(), image_name)
		with open(image_path, "w") as f:
			f.write(image_data)

	def final_restore(self, img, connection):
		"""Perform Virtuozzo-specific final restore"""
		try:
			# Setup restore extra arguments
			args_path = os.path.join(img.image_dir(), "restore-extra-args")
			self.__setup_restore_extra_args(args_path, img, connection)
			# Run vzctl restore
			logging.info("Starting vzctl restore")
			proc = subprocess.Popen([vzctl_bin, "--skipowner", "--skiplock", "restore",
				self._ctid, "--skip_arpdetect", "--dumpfile", img.image_dir()],
				stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
			proc_output = proc.communicate()[0]
			util.log_subprocess_output(proc_output)
			if proc.returncode != 0:
				raise Exception("Restore failed ({0})".format(proc.returncode))
		finally:
			# Remove restore extra arguments
			self.__remove_restore_extra_args(args_path)

	def __setup_restore_extra_args(self, path, img, connection):
		"""Create temporary file with extra arguments for criu restore"""
		extra_args = [
			"VE_WORK_DIR={0}\n".format(img.work_dir()),
			"VE_RESTORE_LOG_PATH={0}\n".format(
				connection.get_log_name(pycriu.rpc.RESTORE)),
			"VE_CRIU_LOGLEVEL={0}\n".format(self.__verbose)]
		with open(path, "w") as f:
			f.writelines(extra_args)

	def __remove_restore_extra_args(self, path):
		"""Remove temporary file with extra arguments for criu restore"""
		if os.path.isfile(path):
			os.remove(path)

	def prepare_ct(self, pid):
		"""Create cgroup hierarchy and put root task into it."""
		self.__cg_set_veid()

	def mount(self):
		logging.info("Mounting CT root to %s", self._ct_root)
		logging.info("Running vzctl mount")
		proc = subprocess.Popen(
			[vzctl_bin, "--skipowner", "--skiplock", "mount", self._ctid],
			stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		proc_output = proc.communicate()[0]
		util.log_subprocess_output(proc_output)
		self._fs_mounted = True
		return self._ct_root

	def umount(self):
		if self._fs_mounted:
			logging.info("Umounting CT root")
			logging.info("Running vzctl umount")
			proc = subprocess.Popen(
				[vzctl_bin, "--skipowner", "--skiplock", "umount", self._ctid],
				stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
			proc_output = proc.communicate()[0]
			util.log_subprocess_output(proc_output)
			self._fs_mounted = False

	def migration_complete(self, fs, target_host):
		fs.cleanup_shared_ploops()
		self.umount()
		target_host.migration_complete(fs.prepare_src_data({}))

	def migration_fail(self, fs):
		fs.restore_shared_ploops()

	def target_cleanup(self, src_data):
		if "shareds" in src_data:
			for ploop in src_data["shareds"]:
				fs_haul_ploop.merge_ploop_snapshot(ploop["ddxml"], ploop["guid"])

	def start(self):
		logging.info("Starting CT")
		logging.info("Running vzctl start")
		proc = subprocess.Popen(
			[vzctl_bin, "--skipowner", "--skiplock", "start", self._ctid],
			stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		proc_output = proc.communicate()[0]
		util.log_subprocess_output(proc_output)
		self._fs_mounted = True

	def stop(self, umount):
		logging.info("Stopping CT")
		logging.info("Running vzctl stop")
		args = [vzctl_bin, "--skipowner", "--skiplock", "stop", self._ctid]
		if not umount:
			args.append("--skip-umount")
		proc = subprocess.Popen(
			args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		proc_output = proc.communicate()[0]
		util.log_subprocess_output(proc_output)
		self._fs_mounted = not umount

	def get_fs(self, fdfs=None):
		deltas = self.__parse_fdfs_arg(fdfs)
		return fs_haul_ploop.p_haul_fs(deltas, self._ct_priv)

	def get_fs_receiver(self, fdfs=None):
		deltas = self.__parse_fdfs_arg(fdfs)
		return fs_haul_ploop.p_haul_fs_receiver(deltas)

	def __parse_fdfs_arg(self, fdfs):
		"""
		Parse string containing list of ploop deltas with socket fds

		String contain list of active ploop deltas with corresponding socket
		file descriptors in format %delta_path1%:%socket_fd1%[,...]. Parse it
		and return list of tuples.
		"""

		FDFS_DELTAS_SEPARATOR = ","
		FDFS_PAIR_SEPARATOR = ":"

		if not fdfs:
			return []

		deltas = []
		for delta in fdfs.split(FDFS_DELTAS_SEPARATOR):
			path, dummy, fd = delta.rpartition(FDFS_PAIR_SEPARATOR)
			deltas.append((fs_haul_ploop.get_delta_abspath(path, self._ct_priv), int(fd)))

		return deltas

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
	parser.add_argument("--vz-shared-disks", help="List of shared storage disks")


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
