#
# The P.HAUL core -- the class that drives migration
#

import images
import mstats
import xem_rpc
import pycriu.rpc as cr_rpc
import criu_api
import p_haul_type

# Constants for iterations management
#
# Maximum number of iterations
phaul_iter_max = 8
# If we dump less than this amount of pages we abort
# iterations and go do the full dump
phaul_iter_min_size = 64
# Each iteration should dump less pages or at most
# this % more than previous
phaul_iter_grow_max = 10

class phaul_iter_worker:
	def __init__(self, p_type, host):
		self._mstat = mstats.migration_stats()
		self.iteration = 0
		self.prev_stats = None

		print "Connecting to target host"
		self.th = xem_rpc.rpc_proxy(host)
		self.data_sk = self.th.open_socket("datask")

		print "Setting up local"
		self.img = images.phaul_images("dmp")
		self.criu = criu_api.criu_conn(self.data_sk)
		self.htype = p_haul_type.get_src(p_type)
		if not self.htype:
			raise Exception("No htype driver found")

		self.fs = self.htype.get_fs()
		if not self.fs:
			raise Exception("No FS driver found")

		self.pid = self.htype.root_task_pid()
		self.fs.set_target_host(host[0])

		print "Setting up remote"
		self.th.setup(p_type)

	def set_options(self, opts):
		self.th.set_options(opts)
		self.criu.verbose(opts["verbose"])
		self.img.set_options(opts)
		self.htype.set_options(opts)
		self.__force = opts["force"]

	def validate_cpu(self):
		print "Checking CPU compatibility"

		print "  `- Dumping CPU info"
		req = self.__make_cpuinfo_dump_req()
		resp = self.criu.send_req(req)
		if not resp.success:
			raise Exception("Can't dump cpuinfo")

		print "  `- Sending CPU info"
		self.img.send_cpuinfo(self.th, self.data_sk)

		print "  `- Checking CPU info"
		if not self.th.check_cpuinfo():
			raise Exception("CPUs mismatch")

	def start_migration(self):
		self._mstat.start()

		if not self.__force:
			self.validate_cpu()

		print "Preliminary FS migration"
		self.fs.set_work_dir(self.img.work_dir())
		self.fs.start_migration()

		print "Starting iterations"

		while True:
			print "* Iteration %d" % self.iteration

			self.th.start_iter()
			self.img.new_image_dir()

			print "\tIssuing pre-dump command to service"

			req = self.__make_predump_req()
			resp = self.criu.send_req(req)
			if not resp.success:
				raise Exception("Pre-dump failed")

			print "\tPre-dump succeeded"

			self.th.end_iter()

			stats = criu_api.criu_get_dstats(self.img)
			self._mstat.iteration(stats)

			#
			# Need to decide whether we do next iteration
			# or stop on the existing and go do full dump
			# and restore
			#

			print "Checking iteration progress:"

			if stats.pages_written <= phaul_iter_min_size:
				print "\t> Small dump"
				break;

			if self.prev_stats:
				w_add = stats.pages_written - self.prev_stats.pages_written
				w_add = w_add * 100 / self.prev_stats.pages_written
				if w_add > phaul_iter_grow_max:
					print "\t> Iteration grows"
					break

			if self.iteration >= phaul_iter_max:
				print "\t> Too many iterations"
				break

			self.iteration += 1
			self.prev_stats = stats
			print "\t> Proceed to next iteration"

			self.fs.next_iteration()

		#
		# Finish with iterations -- do full dump, send images
		# to target host and restore from them there
		#

		print "Final dump and restore"

		self.th.start_iter()
		self.img.new_image_dir()

		print "\tIssuing dump command to service"

		req = self.__make_dump_req()
		resp = self.criu.send_req(req)
		while True:
			if resp.type != cr_rpc.NOTIFY:
				raise Exception("Dump failed")

			if resp.notify.script == "post-dump":
				#
				# Dump is effectively over. Now CRIU
				# waits for us to do whatever we want
				# and keeps the tasks frozen.
				#
				break

			elif resp.notify.script == "network-lock":
				self.htype.net_lock()
			elif resp.notify.script == "network-unlock":
				self.htype.net_unlock()

			print "\t\tNotify (%s)" % resp.notify.script
			resp = self.criu.ack_notify()

		print "Dump complete"
		self.th.end_iter()

		#
		# Dump is complete -- go to target node,
		# restore them there and kill (if required)
		# tasks on source node
		#

		print "Final FS and images sync"
		self.fs.stop_migration()
		self.img.sync_imgs_to_target(self.th, self.htype, self.data_sk)

		print "Asking target host to restore"
		self.th.restore_from_images()

		#
		# Ack the notify after restore -- CRIU would
		# then terminate all tasks and send us back
		# DUMP/success message
		#

		resp = self.criu.ack_notify()
		if not resp.success:
			raise Exception("Dump screwed up")

		self.htype.umount()

		stats = criu_api.criu_get_dstats(self.img)
		self._mstat.iteration(stats)
		self._mstat.stop(self)
		self.img.close()
		self.criu.close()

	def __make_req(self, typ):
		"""Prepare generic criu request"""
		req = cr_rpc.criu_req()
		req.type = typ
		return req

	def __make_common_dump_req(self, typ):
		"""Prepare common criu request for pre-dump or dump"""

		req = self.__make_req(typ)
		req.opts.pid = self.pid
		req.opts.ps.fd = self.criu.mem_sk_fileno()
		req.opts.track_mem = True

		req.opts.images_dir_fd = self.img.image_dir_fd()
		req.opts.work_dir_fd = self.img.work_dir_fd()
		p_img = self.img.prev_image_dir()
		if p_img:
			req.opts.parent_img = p_img
		if not self.fs.persistent_inodes():
			req.opts.force_irmap = True

		return req

	def __make_cpuinfo_dump_req(self):
		"""Prepare cpuinfo dump criu request"""
		req = self.__make_req(cr_rpc.CPUINFO_DUMP)
		req.opts.images_dir_fd = self.img.work_dir_fd()
		req.keep_open = True
		return req

	def __make_predump_req(self):
		"""Prepare pre-dump criu request"""
		return self.__make_common_dump_req(cr_rpc.PRE_DUMP)

	def __make_dump_req(self):
		"""Prepare dump criu request"""
		req = self.__make_common_dump_req(cr_rpc.DUMP)
		req.opts.notify_scripts = True
		req.opts.file_locks = True
		req.opts.evasive_devices = True
		req.opts.link_remap = True
		if self.htype.can_migrate_tcp():
			req.opts.tcp_established = True
		return req
