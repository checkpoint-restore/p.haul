#
# The P.HAUL core -- the class that drives migration
#

import logging
import images
import mstats
import xem_rpc
import pycriu.rpc as cr_rpc
import criu_api
import criu_req
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

		logging.info("Connecting to target host")
		self.th = xem_rpc.rpc_proxy(host)
		self.data_sk = self.th.open_socket("datask")

		logging.info("Setting up local")
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

		logging.info("Setting up remote")
		self.th.setup(p_type)

	def set_options(self, opts):
		self.th.set_options(opts)
		self.criu.verbose(opts["verbose"])
		self.img.set_options(opts)
		self.htype.set_options(opts)
		self.__force = opts["force"]

	def validate_cpu(self):
		logging.info("Checking CPU compatibility")

		logging.info("\t`- Dumping CPU info")
		req = criu_req.make_cpuinfo_dump_req(self.htype, self.img)
		resp = self.criu.send_req(req)
		if not resp.success:
			raise Exception("Can't dump cpuinfo")

		logging.info("\t`- Sending CPU info")
		self.img.send_cpuinfo(self.th, self.data_sk)

		logging.info("\t`- Checking CPU info")
		if not self.th.check_cpuinfo():
			raise Exception("CPUs mismatch")

	def start_migration(self):
		self._mstat.start()

		if not self.__force:
			self.validate_cpu()

		logging.info("Preliminary FS migration")
		self.fs.set_work_dir(self.img.work_dir())
		self.fs.start_migration()

		logging.info("Starting iterations")

		while True:
			logging.info("* Iteration %d", self.iteration)

			self.th.start_iter()
			self.img.new_image_dir()

			logging.info("\tIssuing pre-dump command to service")

			req = criu_req.make_predump_req(
				self.pid, self.htype, self.img, self.criu, self.fs)
			resp = self.criu.send_req(req)
			if not resp.success:
				raise Exception("Pre-dump failed")

			logging.info("\tPre-dump succeeded")

			self.th.end_iter()

			stats = criu_api.criu_get_dstats(self.img)
			self._mstat.iteration(stats)

			#
			# Need to decide whether we do next iteration
			# or stop on the existing and go do full dump
			# and restore
			#

			logging.info("Checking iteration progress:")

			if stats.pages_written <= phaul_iter_min_size:
				logging.info("\t> Small dump")
				break;

			if self.prev_stats:
				w_add = stats.pages_written - self.prev_stats.pages_written
				w_add = w_add * 100 / self.prev_stats.pages_written
				if w_add > phaul_iter_grow_max:
					logging.info("\t> Iteration grows")
					break

			if self.iteration >= phaul_iter_max:
				logging.info("\t> Too many iterations")
				break

			self.iteration += 1
			self.prev_stats = stats
			logging.info("\t> Proceed to next iteration")

			self.fs.next_iteration()

		#
		# Finish with iterations -- do full dump, send images
		# to target host and restore from them there
		#

		logging.info("Final dump and restore")

		self.th.start_iter()
		self.img.new_image_dir()

		logging.info("\tIssuing dump command to service")

		req = criu_req.make_dump_req(
			self.pid, self.htype, self.img, self.criu, self.fs)
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

			logging.info("\t\tNotify (%s)", resp.notify.script)
			resp = self.criu.ack_notify()

		logging.info("Dump complete")
		self.th.end_iter()

		#
		# Dump is complete -- go to target node,
		# restore them there and kill (if required)
		# tasks on source node
		#

		logging.info("Final FS and images sync")
		self.fs.stop_migration()
		self.img.sync_imgs_to_target(self.th, self.htype, self.data_sk)

		logging.info("Asking target host to restore")
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
