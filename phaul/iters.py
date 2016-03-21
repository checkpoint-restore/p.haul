#
# The P.HAUL core -- the class that drives migration
#

import logging
import images
import mstats
import xem_rpc_client
import criu_api
import criu_cr
import criu_req
import htype
import errno


MIGRATION_MODE_LIVE = "live"
MIGRATION_MODE_RESTART = "restart"
MIGRATION_MODES = (MIGRATION_MODE_LIVE, MIGRATION_MODE_RESTART)

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
	def __init__(self, p_type, mode, connection):
		self.__mode = mode
		self.connection = connection
		self.target_host = xem_rpc_client.rpc_proxy(self.connection.rpc_sk)

		logging.info("Setting up local")
		self.criu_connection = criu_api.criu_conn(self.connection.mem_sk)
		self.img = images.phaul_images("dmp")

		self.htype = htype.get_src(p_type)
		if not self.htype:
			raise Exception("No htype driver found")

		self.fs = self.htype.get_fs(self.connection.fdfs)
		if not self.fs:
			raise Exception("No FS driver found")

		logging.info("Setting up remote")
		self.target_host.setup(p_type)

	def get_target_host(self):
		return self.target_host

	def set_options(self, opts):
		self.__force = opts["force"]
		self.__pre_dump = opts["pre_dump"]
		self.target_host.set_options(opts)
		self.criu_connection.set_options(opts)
		self.img.set_options(opts)
		self.htype.set_options(opts)
		self.fs.set_options(opts)

	def __validate_cpu(self):
		if self.__force:
			return
		logging.info("Checking CPU compatibility")

		logging.info("\t`- Dumping CPU info")
		req = criu_req.make_cpuinfo_dump_req(self.img)
		resp = self.criu_connection.send_req(req)
		if resp.HasField('cr_errno') and (resp.cr_errno == errno.ENOTSUP):
			logging.info("\t`- Dumping CPU info not supported")
			self.__force = True
			return
		if not resp.success:
			raise Exception("Can't dump cpuinfo")

		logging.info("\t`- Sending CPU info")
		self.img.send_cpuinfo(self.target_host, self.connection.mem_sk)

		logging.info("\t`- Checking CPU info")
		if not self.target_host.check_cpuinfo():
			raise Exception("CPUs mismatch")

	def __check_support_mem_track(self):
		req = criu_req.make_dirty_tracking_req(self.img)
		resp = self.criu_connection.send_req(req)
		if not resp.success:
			raise Exception()
		if not resp.HasField('features'):
			return False
		if not resp.features.HasField('mem_track'):
			return False
		return resp.features.mem_track

	def __check_use_pre_dumps(self):
		logging.info("Checking for Dirty Tracking")
		use_pre_dumps = False
		if self.__pre_dump == PRE_DUMP_AUTO_DETECT:
			try:
				# Detect is memory tracking supported
				use_pre_dumps = (self.__check_support_mem_track() and
					self.htype.can_pre_dump())
				logging.info("\t`- Auto %s",
					(use_pre_dumps and "enabled" or "disabled"))
			except:
				# Memory tracking auto detection not supported
				use_pre_dumps = False
				logging.info("\t`- Auto detection not possible - Disabled")
		else:
			use_pre_dumps = self.__pre_dump
			logging.info("\t`- Explicitly %s",
				(use_pre_dumps and "enabled" or "disabled"))
		self.criu_connection.memory_tracking(use_pre_dumps)
		return use_pre_dumps

	def start_migration(self):
		logging.info("Start migration in %s mode", self.__mode)
		if self.__mode == MIGRATION_MODE_LIVE:
			self.__start_live_migration()
		elif self.__mode == MIGRATION_MODE_RESTART:
			self.__start_restart_migration()
		else:
			raise Exception("Unknown migration mode")

	def __start_live_migration(self):
		"""
		Start migration in live mode

		Migrate memory and fs to target host iteratively while possible,
		checkpoint process tree on source host and restore it on target host.
		"""

		self.fs.set_work_dir(self.img.work_dir())
		self.__validate_cpu()
		use_pre_dumps = self.__check_use_pre_dumps()
		root_pid = self.htype.root_task_pid()

		migration_stats = mstats.live_stats()
		migration_stats.handle_start()

		# Handle preliminary FS migration
		logging.info("Preliminary FS migration")
		fsstats = self.fs.start_migration()
		migration_stats.handle_preliminary(fsstats)

		iter_index = 0
		prev_dstats = None

		while use_pre_dumps:

			# Handle predump
			logging.info("* Iteration %d", iter_index)
			self.target_host.start_iter(True)
			self.img.new_image_dir()
			criu_cr.criu_predump(root_pid, self.img, self.criu_connection, self.fs)
			self.target_host.end_iter()

			# Handle FS migration iteration
			fsstats = self.fs.next_iteration()

			dstats = criu_api.criu_get_dstats(self.img)
			migration_stats.handle_iteration(dstats, fsstats)

			# Decide whether we continue iteration or stop and do final dump
			if not self.__check_live_iter_progress(iter_index, dstats, prev_dstats):
				break

			iter_index += 1
			prev_dstats = dstats

		# Dump htype on source and leave its tasks in frozen state
		logging.info("Final dump and restore")
		self.target_host.start_iter(self.htype.dump_need_page_server())
		self.img.new_image_dir()
		self.htype.final_dump(root_pid, self.img, self.criu_connection, self.fs)
		self.target_host.end_iter()

		# Handle final FS and images sync on frozen htype
		logging.info("Final FS and images sync")
		fsstats = self.fs.stop_migration()
		self.img.sync_imgs_to_target(self.target_host, self.htype,
			self.connection.mem_sk)

		# Restore htype on target
		logging.info("Asking target host to restore")
		self.target_host.restore_from_images()

		# Ack previous dump request to terminate all frozen tasks
		logging.info("Restored on target host")
		resp = self.criu_connection.ack_notify()
		if not resp.success:
			raise Exception("Dump screwed up")

		dstats = criu_api.criu_get_dstats(self.img)
		migration_stats.handle_iteration(dstats, fsstats)

		logging.info("Migration succeeded")
		self.htype.umount()
		migration_stats.handle_stop(self)
		self.img.close()
		self.criu_connection.close()

	def __start_restart_migration(self):
		"""
		Start migration in restart mode

		Migrate fs to target host iteratively while possible, stop process
		tree on source host and start it on target host.
		"""

		raise Exception("Not implemented")

	def __check_live_iter_progress(self, index, dstats, prev_dstats):

		logging.info("Checking iteration progress:")

		if dstats.pages_written <= phaul_iter_min_size:
			logging.info("\t> Small dump")
			return False

		if prev_dstats:
			w_add = dstats.pages_written - prev_dstats.pages_written
			w_add = w_add * 100 / prev_dstats.pages_written
			if w_add > phaul_iter_grow_max:
				logging.info("\t> Iteration grows")
				return False

		if index >= phaul_iter_max:
			logging.info("\t> Too many iterations")
			return False

		logging.info("\t> Proceed to next iteration")
		return True
