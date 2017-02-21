#
# Runc container hauler
#

import json
import logging
import os
import pwd
import re
import shutil
import subprocess as sp

import pycriu

import criu_cr
import fs_haul_subtree


# Some constants for runc
runc_bin = "/usr/bin/runc"  # "/usr/local/sbin/runc" for compiled version
runc_run = "/var/run/runc/"
runc_conf_name = "config.json"


class p_haul_type(object):
	def __init__(self, ctid):

		# Validate provided container ID
		if (not(re.match("^[\w-]+$", ctid)) or len(ctid) > 1024):
			raise Exception("Invalid runc container name: %s", ctid)

		self._ctid = ctid
		self._veths = []
		self._binds = {}
		self._inherit_fd = {}

	def _parse_self_cgroup(self):
		# Get pairs of {subsystem: root}
		cgroups = {}
		with open("/proc/self/cgroup", "r") as proc_cgroups:
			for line in proc_cgroups.readlines():
				parts = line.split(":")
				if len(parts) < 3:
					logging.error("Invalid cgroup: %s", line)
				else:
					subsystems = parts[1].split(",")
					for subsystem in subsystems:
						cgroups.update(
							{re.sub("name=", "",
							subsystem): parts[2]})
		return cgroups

	def init_src(self):
		try:
			with open(os.path.join(runc_run, self._ctid, "state.json"), "r") as state:
				self._container_state = json.loads(state.read())
			self._labels = self._container_state["config"]["labels"]
			self._ct_rootfs = self._container_state["config"]["rootfs"]
			self._root_pid = self._container_state["init_process_pid"]
			self._ext_descriptors = json.dumps(
				self._container_state["external_descriptors"])
		except IOError:
			raise Exception("No container %s is running", self._ctid)
		except KeyError:
			raise Exception("Invalid container state retrieved")

		self._runc_bundle = next(label[len("bundle="):]
						for label in self._labels
						if label.startswith("bundle="))

		if any([mount["device"] == "cgroup" for mount in
				self._container_state["config"]["mounts"]]):
			cgroup_paths = self._container_state["cgroup_paths"]
		for mount in self._container_state["config"]["mounts"]:
			if mount["device"] == "bind":
				if mount["destination"].startswith(self._ct_rootfs):
					dst = mount["destination"][len(self._ct_rootfs):]
				else:
					dst = mount["destination"]
				self._binds.update({dst: dst})
			if mount["device"] == "cgroup":
				for subsystem, c_mp in cgroup_paths.items():
					# Remove container ID from path
					mountpoint = os.path.split(c_mp)[0]
					dst = os.path.join(mount["destination"],
							os.path.split(mountpoint)[0])
					if dst.startswith(self._ct_rootfs):
						dst = dst[len(self._ct_rootfs):]
					self._binds.update({dst: dst})

		if self._container_state["config"]["mask_paths"] is not None:
			masked = self._container_state["config"]["mask_paths"]
			for path in masked:
				filepath = os.path.join("/proc", self.root_task_pid, "root", path)
				if (os.path.exists(filepath) and
						not os.path.isdir(filepath)):
					self._binds.update({path: "/dev/null"})

		self.__load_ct_config(self._runc_bundle)
		logging.info("Container rootfs: %s", self._ct_rootfs)

	def init_dst(self):
		if os.path.exists(os.path.join(runc_run, self._ctid)):
			raise Exception("Container with same ID already exists")

	def adjust_criu_req(self, req):
		if req.type in [pycriu.rpc.DUMP, pycriu.rpc.RESTORE]:
			req.opts.manage_cgroups = True
			req.opts.notify_scripts = True
			for key, value in self._binds.items():
				req.opts.ext_mnt.add(key=key, val=value)

		if req.type == pycriu.rpc.RESTORE:
			req.opts.root = self._ct_rootfs
			req.opts.rst_sibling = True
			req.opts.evasive_devices = True
			for key, value in self._inherit_fd.items():
				req.opts.inherit_fd.add(key=key, fd=value)

	def root_task_pid(self):
		return self._root_pid

	def __load_ct_config(self, path):
		self._ct_config = os.path.join(self._runc_bundle, runc_conf_name)
		logging.info("Container config: %s", self._ct_config)

	def set_options(self, opts):
		pass

	def prepare_ct(self, pid):
		pass

	def mount(self):
		nroot = os.path.join(self._runc_bundle, "criu_dir")
		if not os.access(nroot, os.F_OK):
			os.makedirs(nroot)
		sp.call(["mount", "--bind", self._ct_rootfs, nroot])
		return nroot

	def umount(self):
		nroot = os.path.join(self._runc_bundle, "criu_dir")
		if os.path.exists(nroot):
			sp.call(["umount", nroot])
			shutil.rmtree(nroot)

	def start(self):
		pass

	def stop(self, umount):
		pass

	def get_fs(self, fdfs=None):
		return fs_haul_subtree.p_haul_fs([self._ct_rootfs, self._ct_config])

	def get_fs_receiver(self, fdfs=None):
		return None

	def get_meta_images(self, path):
		bundle_path = os.path.join(path, "bundle.txt")
		with open(bundle_path, "w+") as bundle_file:
			bundle_file.write(self._runc_bundle)
		desc_path = os.path.join(path, "descriptors.json")
		with open(desc_path, "w+") as desc_file:
			desc_file.write(self._ext_descriptors)
		shutil.copy(os.path.join(runc_run, self._ctid, "state.json"), path)
		return [(bundle_path, "bundle.txt"),
				(desc_path, "descriptors.json"),
				(os.path.join(path, "state.json"), "state.json")]

	def put_meta_images(self, dir):
		with open(os.path.join(dir, "bundle.txt")) as bundle_file:
			self._runc_bundle = bundle_file.read()

	def final_dump(self, pid, img, ccon, fs):
		criu_cr.criu_dump(self, pid, img, ccon, fs)

	def migration_complete(self, fs, target_host):
		sp.call([runc_bin, "delete", self._ctid])

	def migration_fail(self, fs):
		p_haul_user = pwd.getpwuid(os.geteuid()).pw_name
		sp.call(["ssh", p_haul_user + "@" + fs._p_haul_fs__thost,
			"rm -r", self._runc_bundle + "/*"])

	def target_cleanup(self, src_data):
		pass

	def final_restore(self, img, connection):
		try:
			with open(os.path.join(self._runc_bundle, runc_conf_name), "r") as config:
				self._container_state = json.loads(config.read())
			root_path = self._container_state["root"]["path"]
		except IOError:
			raise Exception("Unable to get container config")
		except KeyError:
			raise Exception("Invalid config")

		if not os.path.isabs(root_path):
			self._ct_rootfs = os.path.join(self._runc_bundle, root_path)
		else:
			self._ct_rootfs = root_path

		if any([mount["type"] == "cgroup" for mount in
				self._container_state["mounts"]]):
			self_cgroups = self._parse_self_cgroup()
			cgroup_paths = self._container_state["cgroup_paths"]
		for mount in self._container_state["mounts"]:
			if mount["type"] == "bind":
				if mount["destination"].startswith(self._ct_rootfs):
					dst = mount["destination"][len(self._ct_rootfs):]
				else:
					dst = mount["destination"]
				self._binds.update({dst: mount["source"]})
			if mount["type"] == "cgroup":
				with open("/proc/self/mountinfo", "r") as mountinfo:
					lines = mountinfo.readlines()
				for subsystem, c_mp in cgroup_paths.items():
					# Remove container ID from path
					mountpoint = os.path.split(c_mp)[0]
					dst = os.path.join(mount["destination"],
							os.path.split(mountpoint)[0])
					if dst.startswith(self._ct_rootfs):
						dst = dst[len(self._ct_rootfs):]
					line = next(line for line in lines
							if mountpoint in line)
					src = os.path.join(mountpoint,
						os.path.relpath(
							self_cgroups[subsystem],
							line.split()[3]))
					self._binds.update({dst: src})

		with open(os.path.join(img.image_dir(), "descriptors.json"), "r") as descr:
			inherits = [(dsc, i) for i, dsc in
					enumerate(json.loads(descr.read()))
					if "pipe:" in dsc]
		for dsc, i in inherits:
			self._inherit_fd.update({dsc: i})

		with open(os.path.join(img.image_dir(), "state.json"), "r") as old_state_file:
			self._restore_state = json.loads(old_state_file.read())

		criu_cr.criu_restore(self, img, connection)

	def restored(self, pid):
		self._restore_state["init_process_pid"] = pid
		ct_path = os.path.join(runc_run, self._ctid)
		if not os.path.exists(ct_path):
			os.makedirs(ct_path, 0711)
		else:
			raise Exception("Container with same ID already exists")
		with open(os.path.join(runc_run, self._ctid, "state.json"),
				"w+") as new_state_file:
			new_state_file.write(json.dumps(self._restore_state))
		self.umount()

	def can_pre_dump(self):
		return True

	def dump_need_page_server(self):
		return True

	def can_migrate_tcp(self):
		return False

	def veths(self):
		return self._veths

	def run_action_scripts(self, stage):
		pass
