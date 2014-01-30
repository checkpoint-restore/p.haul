#
# The P.HAUL core -- the class that drives migration
#

import time
import rpyc
import rpc_pb2 as cr_rpc
import p_haul_criu as cr_api

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

		self.htype = p_type
		self.pid = p_type.root_task_pid()
		print "\tWill work on %d task\n" % self.pid

	def make_dump_req(self, typ):
		#
		# Prepare generic request for (pre)dump
		#

		req = cr_rpc.criu_req()
		req.type = typ
		req.opts.pid = self.pid
		req.opts.ps.address = self.target_host
		req.opts.ps.port = self.th.get_ps_port()
		req.opts.track_mem = True

		req.opts.images_dir_fd = self.img.image_dir_fd()
		p_img = self.img.prev_image_dir()
		if p_img:
			req.opts.parent_img = p_img

		return req

	def start_migration(self):
		print "Connecting to CRIU service"
		cc = cr_api.criu_conn()

		print "Connecting to target host"
		th_con = rpyc.connect(self.target_host, rpyc_target_port)
		self.th = th_con.root
		self.th.set_htype(self.htype.id())

		start_time = time.time()

		print "Starting iterations"
		while True:
			print "* Iteration %d" % self.iteration

			self.th.start_iter()
			self.img.new_image_dir()

			print "\tIssuing pre-dump command to service"

			req = self.make_dump_req(cr_rpc.PRE_DUMP)
			resp = cc.send_req(req)
			if (resp.type != cr_rpc.DUMP) or (not resp.success):
				print "\tPre-dump failed"
				raise 1

			print "\tPre-dump succeeded"

			self.th.end_iter()

			stats = cr_api.criu_get_dstats(self.img.image_dir())
			print "Dumped %d pages, %d skipped" % \
					(stats.pages_written, stats.pages_skipped_parent)

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
		cc.send_req(req, False)

		while True:
			resp = cc.recv_resp()
			if resp.type != cr_rpc.NOTIFY:
				print "Unexpected responce from service"
				raise 1
			if resp.notify.script == "post-dump":
				#
				# Dump is effectively over. Now CRIU
				# waits for us to do whatever we want
				# and keeps the tasks frozen.
				#
				break
			print "\t\tNotify"
			cc.ack_notify()

		print "Dump complete"
		self.th.end_iter()

		#
		# Dump is complete -- go to target node,
		# restore them there and kill (if required)
		# tasks on source node
		#

		self.img.sync_imgs_to_target(self.th, self.htype)

		print "Asking target host to restore"
		self.th.restore_from_images()
		cc.ack_notify()
		resp = cc.recv_resp()
		if resp.type != cr_rpc.DUMP:
			print "\tDump failed"
			raise 1

		end_time = time.time()

		stats = cr_api.criu_get_dstats(self.img.image_dir())
		print "Final dump -- %d pages, %d skipped" % \
				(stats.pages_written, stats.pages_skipped_parent)
		self.frozen_time += stats.frozen_time
		self.img.close()

		rst_time = self.th.restore_time()
		print "Migration succeeded"
		print "\t  total time is ~%.2lf sec" % (end_time - start_time)
		print "\t frozen time is ~%.2lf sec" % (self.frozen_time / 1000000.)
		print "\trestore time is ~%.2lf sec" % (rst_time / 1000000.)
