#
# P.HAUL code, that helps on the target node (rpyc service)
#

import rpyc, rpc_pb2 as cr_rpc, os
import p_haul_img as ph_img
import p_haul_criu as cr_api

ps_start_port = 12345

class phaul_service(rpyc.Service):
	def on_connect(self):
		print "Connected"
		self.dump_iter = 0
		self.page_server_pid = 0
		self.img = ph_img.phaul_images() # FIXME -- get images driver from client

	def on_disconnect(self):
		print "Disconnected"
		if self.page_server_pid:
			print "Sopping page server %d" % self.page_server_pid
			os.kill(self.page_server_pid, 9)

		print "Closing images"
		self.img.close()

	def start_page_server(self):
		print "Starting page server for iter %d" % self.dump_iter
		cc = cr_api.criu_conn()

		req = cr_rpc.criu_req()
		req.type = cr_rpc.PAGE_SERVER
		req.opts.ps.port = ps_start_port + self.dump_iter # FIXME -- implement and use autobind in CRIU

		req.opts.images_dir_fd = self.img.image_dir_fd()
		p_img = self.img.prev_image_dir()
		if p_img:
			req.opts.parent_img = p_img

		print "\tSending criu rpc req"
		resp = cc.send_req(req)
		if (resp.type != cr_rpc.PAGE_SERVER) or (not resp.success):
			print "\tFailed to start page server"
			raise 1

		self.page_server_pid = resp.ps.pid
		print "\tPage server started at %d" % resp.ps.pid

	def exposed_start_iter(self):
		self.dump_iter += 1
		self.img.new_image_dir()
		self.start_page_server()

	def exposed_end_iter(self):
		self.page_server_pid = 0

	def exposed_get_ps_port(self):
		return ps_start_port + self.dump_iter

	def exposed_restore_from_images(self):
		print "Restoring from images"
		cc = cr_api.criu_conn()

		req = cr_rpc.criu_req()
		req.type = cr_rpc.RESTORE
		req.opts.images_dir_fd = self.img.image_dir_fd()

		resp = cc.send_req(req)
		if (resp.type != cr_rpc.RESTORE) or (not resp.success):
			print "\tFailed to restore"
			raise 1

	def exposed_restore_time(self):
		stats = cr_api.criu_get_rstats(self.img.image_dir())
		return stats.restore_time

	def exposed_open_image_tar(self):
		return ph_img.exposed_images_tar(self.img.image_dir())
