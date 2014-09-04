#
# The P.HAUL core -- the class that drives migration
#

import time
import rpyc
import rpc_pb2 as cr_rpc
import p_haul_criu as cr_api
import p_haul_socket as ph_sk

rpyc_target_port = 18861

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
	def __init__(self, p_type, host, img):
		self.frozen_time = 0
		self.iteration = 0
		self.prev_stats = None
		self.target_host = host
		self.img = img.phaul_images()

		print "Connecting to target host"
		self.th_con = rpyc.connect(self.target_host, rpyc_target_port)
		self.th = self.th_con.root

		self.htype = p_type
		self.th.htype(p_type.id())

		self.pid = p_type.root_task_pid()
		self.fs = p_type.get_fs()
		if not self.fs:
			raise Exception("No FS driver found")

		self.fs.set_target_host(host)

		mem_sk = ph_sk.create(self.target_host)
		self.th.accept_mem_sk(mem_sk.name())
		self.criu = cr_api.criu_conn(mem_sk)

	def make_dump_req(self, typ):
		#
		# Prepare generic request for (pre)dump
		#

		req = cr_rpc.criu_req()
		req.type = typ
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

	def verbose(self, level):
		self.criu.verbose(level)
		self.th.verbose(level)

	def keep_images(self, val):
		self.keep_images = val
		self.th.keep_images(self.keep_images)

	def start_migration(self):
		start_time = time.time()
		iter_times = []

		print "Preliminary FS migration"
		self.fs.set_work_dir(self.img.work_dir())
		self.fs.start_migration()

		print "Starting iterations"
		cc = self.criu

		while True:
			print "* Iteration %d" % self.iteration

			self.th.start_iter()
			self.img.new_image_dir()

			print "\tIssuing pre-dump command to service"

			req = self.make_dump_req(cr_rpc.PRE_DUMP)
			resp = cc.send_req(req)
			if (resp.type != cr_rpc.PRE_DUMP) or (not resp.success):
				raise Exception("Pre-dump failed")

			print "\tPre-dump succeeded"

			self.th.end_iter()

			stats = cr_api.criu_get_dstats(self.img)
			print "Dumped %d pages, %d skipped" % \
					(stats.pages_written, stats.pages_skipped_parent)

			iter_times.append("%.2lf" % (stats.frozen_time / 1000000.))
			self.frozen_time += stats.frozen_time

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
		req = self.make_dump_req(cr_rpc.DUMP)
		req.opts.notify_scripts = True
		req.opts.file_locks = True
		req.opts.evasive_devices = True
		req.opts.link_remap = True
		if self.htype.can_migrate_tcp():
			req.opts.tcp_established = True

		cc.send_req(req, False)

		while True:
			resp = cc.recv_resp()
			if resp.type != cr_rpc.NOTIFY:
				if resp.type == cr_rpc.DUMP and not resp.success:
					raise Exception("Dump failed")
				else:
					raise Exception("Unexpected responce from service (%d)" % resp.type)

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
			cc.ack_notify()

		print "Dump complete"
		self.th.end_iter()

		#
		# Dump is complete -- go to target node,
		# restore them there and kill (if required)
		# tasks on source node
		#

		print "Final FS and images sync"
		self.fs.stop_migration()
		self.img.sync_imgs_to_target(self.th, self.htype)

		print "Asking target host to restore"
		self.th.restore_from_images()

		#
		# Ack the notify after restore -- CRIU would
		# then terminate all tasks and send us back
		# DUMP/success message
		#

		cc.ack_notify()
		resp = cc.recv_resp()
		if resp.type != cr_rpc.DUMP:
			raise Exception("Dump failed")

		self.htype.umount()

		end_time = time.time()

		stats = cr_api.criu_get_dstats(self.img)
		print "Final dump -- %d pages, %d skipped" % \
				(stats.pages_written, stats.pages_skipped_parent)
		iter_times.append("%.2lf" % (stats.frozen_time / 1000000.))
		self.frozen_time += stats.frozen_time
		self.img.close(self.keep_images)
		cc.close()

		rst_time = self.th.restore_time()
		print "Migration succeeded"
		print "\t   total time is ~%.2lf sec" % (end_time - start_time)
		print "\t  frozen time is ~%.2lf sec (" % (self.frozen_time / 1000000.), iter_times, ")"
		print "\t restore time is ~%.2lf sec" % (rst_time / 1000000.)
		print "\timg sync time is ~%.2lf sec" % (self.img.img_sync_time())
