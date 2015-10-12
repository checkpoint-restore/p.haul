#
# The P.HAUL core -- the class that drives migration
#

import logging
import images
import mstats
import xem_rpc_client
import pycriu
import criu_api
import criu_req
import p_haul_type

PRE_DUMP_AUTO_DETECT = None
PRE_DUMP_DISABLE = False
PRE_DUMP_ENABLE = True

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
	def __init__(self, p_type, connection):
		self.connection = connection
		self.target_host = xem_rpc_client.rpc_proxy(self.connection.rpc_sk)

		logging.info("Setting up local")
		self.criu_connection = criu_api.criu_conn(self.connection.mem_sk)
		self.img = images.phaul_images("dmp")

		self.htype = p_haul_type.get_src(p_type)
		if not self.htype:
			raise Exception("No htype driver found")

		self.fs = self.htype.get_fs()
		if not self.fs:
			raise Exception("No FS driver found")

		self.pid = self.htype.root_task_pid()

		self.pre_dump = PRE_DUMP_AUTO_DETECT

		logging.info("Setting up remote")
		self.target_host.setup(p_type)

	def get_target_host(self):
		return self.target_host

	def set_options(self, opts):
		self.target_host.set_options(opts)
		self.criu_connection.verbose(opts["verbose"])
		self.criu_connection.shell_job(opts["shell_job"])
		self.img.set_options(opts)
		self.htype.set_options(opts)
		self.fs.set_options(opts)
		self.__force = opts["force"]
		self.pre_dump = opts["pre_dump"]

	def validate_cpu(self):
		logging.info("Checking CPU compatibility")

		logging.info("\t`- Dumping CPU info")
		req = criu_req.make_cpuinfo_dump_req(self.htype, self.img)
		resp = self.criu_connection.send_req(req)
		if not resp.success:
			raise Exception("Can't dump cpuinfo")

		logging.info("\t`- Sending CPU info")
		self.img.send_cpuinfo(self.target_host, self.connection.mem_sk)

		logging.info("\t`- Checking CPU info")
		if not self.target_host.check_cpuinfo():
			raise Exception("CPUs mismatch")

	def start_migration(self):

		migration_stats = mstats.migration_stats()
		prev_dstats = None
		iter_index = 0

		migration_stats.start()

		if not self.__force:
			self.validate_cpu()

		logging.info("Preliminary FS migration")
		self.fs.set_work_dir(self.img.work_dir())
		self.fs.start_migration()

		if self.pre_dump == PRE_DUMP_AUTO_DETECT:
			# pre-dump auto-detection
			logging.info("Checking for Dirty Tracking")
			req = criu_req.make_dirty_tracking_req(self.htype, self.img)
			resp = self.criu_connection.send_req(req)
			self.pre_dump = resp.success
		elif self.pre_dump == PRE_DUMP_DISABLE:
			self.pre_dump = False
		else:
			self.pre_dump = True

		if resp.success:
			if resp.HasField('features'):
				if resp.features.HasField('mem_track'):
					if resp.features.mem_track:
						logging.info("Starting iterations")
						self.pre_dump = True
			else:
				self.criu_connection.memory_tracking(False)
		else:
			self.criu_connection.memory_tracking(False)

		while self.pre_dump:
			logging.info("* Iteration %d", iter_index)

			self.target_host.start_iter()
			self.img.new_image_dir()

			logging.info("\tIssuing pre-dump command to service")

			req = criu_req.make_predump_req(
				self.pid, self.htype, self.img, self.criu_connection, self.fs)
			resp = self.criu_connection.send_req(req)
			if not resp.success:
				raise Exception("Pre-dump failed")

			logging.info("\tPre-dump succeeded")

			self.target_host.end_iter()

			dstats = criu_api.criu_get_dstats(self.img)
			migration_stats.iteration(dstats)

			#
			# Need to decide whether we do next iteration
			# or stop on the existing and go do full dump
			# and restore
			#

			logging.info("Checking iteration progress:")

			if dstats.pages_written <= phaul_iter_min_size:
				logging.info("\t> Small dump")
				break;

			if prev_dstats:
				w_add = dstats.pages_written - prev_dstats.pages_written
				w_add = w_add * 100 / prev_dstats.pages_written
				if w_add > phaul_iter_grow_max:
					logging.info("\t> Iteration grows")
					break

			if iter_index >= phaul_iter_max:
				logging.info("\t> Too many iterations")
				break

			iter_index += 1
			prev_dstats = dstats
			logging.info("\t> Proceed to next iteration")

			self.fs.next_iteration()

		#
		# Finish with iterations -- do full dump, send images
		# to target host and restore from them there
		#

		logging.info("Final dump and restore")

		self.target_host.start_iter()
		self.img.new_image_dir()

		logging.info("\tIssuing dump command to service")

		req = criu_req.make_dump_req(
			self.pid, self.htype, self.img, self.criu_connection, self.fs)
		resp = self.criu_connection.send_req(req)
		while True:
			if resp.type != pycriu.rpc.NOTIFY:
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
			resp = self.criu_connection.ack_notify()

		logging.info("Dump complete")
		self.target_host.end_iter()

		#
		# Dump is complete -- go to target node,
		# restore them there and kill (if required)
		# tasks on source node
		#

		logging.info("Final FS and images sync")
		self.fs.stop_migration()
		self.img.sync_imgs_to_target(self.target_host, self.htype,
			self.connection.mem_sk)

		logging.info("Asking target host to restore")
		self.target_host.restore_from_images()

		#
		# Ack the notify after restore -- CRIU would
		# then terminate all tasks and send us back
		# DUMP/success message
		#

		resp = self.criu_connection.ack_notify()
		if not resp.success:
			raise Exception("Dump screwed up")

		self.htype.umount()

		dstats = criu_api.criu_get_dstats(self.img)
		migration_stats.iteration(dstats)
		migration_stats.stop(self)
		self.img.close()
		self.criu_connection.close()
