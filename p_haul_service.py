#
# P.HAUL code, that helps on the target node (rpyc service)
#

import xem_rpc
import rpc_pb2 as cr_rpc
import images
import criu_api
import p_haul_type

class phaul_service:
	def on_connect(self):
		print "Connected"
		self.dump_iter = 0
		self.restored = False
		self.criu = None
		self.data_sk = None
		self.img = None
		self.htype = None

	def on_disconnect(self):
		print "Disconnected"
		if self.criu:
			self.criu.close()

		if self.data_sk:
			self.data_sk.close()

		if self.htype and not self.restored:
			self.htype.umount()

		if self.img:
			print "Closing images"
			if not self.restored:
				self.img.save_images()
			self.img.close()

	def on_socket_open(self, sk, uname):
		self.data_sk = sk
		print "Data socket (%s) accepted" % uname

	def rpc_setup(self, htype_id):
		print "Setting up service side", htype_id
		self.img = images.phaul_images("rst")
		self.criu = criu_api.criu_conn(self.data_sk)
		self.htype = p_haul_type.get_dst(htype_id)

	def rpc_set_options(self, opts):
		self.criu.verbose(opts["verbose"])
		self.img.set_options(opts)
		self.htype.set_options(opts)

	def start_page_server(self):
		print "Starting page server for iter %d" % self.dump_iter

		req = cr_rpc.criu_req()
		req.type = cr_rpc.PAGE_SERVER
		req.keep_open = True
		req.opts.ps.fd = self.criu.mem_sk_fileno()

		req.opts.images_dir_fd = self.img.image_dir_fd()
		req.opts.work_dir_fd = self.img.work_dir_fd()
		p_img = self.img.prev_image_dir()
		if p_img:
			req.opts.parent_img = p_img

		print "\tSending criu rpc req"
		resp = self.criu.send_req(req)
		if not resp.success:
			raise Exception("Failed to start page server")

		print "\tPage server started at %d" % resp.ps.pid

	def rpc_start_iter(self):
		self.dump_iter += 1
		self.img.new_image_dir()
		self.start_page_server()

	def rpc_end_iter(self):
		pass

	def rpc_start_accept_images(self, dir_id):
		self.img.start_accept_images(dir_id, self.data_sk)

	def rpc_stop_accept_images(self):
		self.img.stop_accept_images()

	def rpc_check_cpuinfo(self):
		print "Checking cpuinfo"
		req = cr_rpc.criu_req()
		req.type = cr_rpc.CPUINFO_CHECK
		req.opts.images_dir_fd = self.img.work_dir_fd()
		req.keep_open = True
		resp = self.criu.send_req(req)
		print "   `-", resp.success
		return resp.success

	def rpc_restore_from_images(self):
		print "Restoring from images"
		self.htype.put_meta_images(self.img.image_dir())

		req = cr_rpc.criu_req()
		req.type = cr_rpc.RESTORE
		req.opts.images_dir_fd = self.img.image_dir_fd()
		req.opts.work_dir_fd = self.img.work_dir_fd()
		req.opts.notify_scripts = True

		if self.htype.can_migrate_tcp():
			req.opts.tcp_established = True

		for veth in self.htype.veths():
			v = req.opts.veths.add()
			v.if_in = veth.name
			v.if_out = veth.pair

		nroot = self.htype.mount()
		if nroot:
			req.opts.root = nroot
			print "Restore root set to %s" % req.opts.root

		cc = self.criu
		resp = cc.send_req(req)
		while True:
			if resp.type == cr_rpc.NOTIFY:
				print "\t\tNotify (%s.%d)" % (resp.notify.script, resp.notify.pid)
				if resp.notify.script == "setup-namespaces":
					#
					# At that point we have only one task
					# living in namespaces and waiting for
					# us to ACK the notify. Htype might want
					# to configure namespace (external net
					# devices) and cgroups
					#
					self.htype.prepare_ct(resp.notify.pid)
				elif resp.notify.script == "network-unlock":
					self.htype.net_unlock()
				elif resp.notify.script == "network-lock":
					raise Exception("Locking network on restore?")

				resp = cc.ack_notify()
				continue

			if not resp.success:
				raise Exception("Restore failed")

			print "Restore succeeded"
			break

		self.htype.restored(resp.restore.pid)
		self.restored = True

	def rpc_restore_time(self):
		stats = criu_api.criu_get_rstats(self.img)
		return stats.restore_time
