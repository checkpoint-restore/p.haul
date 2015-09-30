#
# P.HAUL code, that helps on the target node (rpyc service)
#

import logging
import xem_rpc
import pycriu.rpc as cr_rpc
import images
import criu_api
import criu_req
import p_haul_type

class phaul_service:
	def on_connect(self):
		logging.info("Connected")
		self.dump_iter = 0
		self.restored = False
		self.criu = None
		self.data_sk = None
		self.img = None
		self.htype = None

	def on_disconnect(self):
		logging.info("Disconnected")
		if self.criu:
			self.criu.close()

		if self.data_sk:
			self.data_sk.close()

		if self.htype and not self.restored:
			self.htype.umount()

		if self.img:
			logging.info("Closing images")
			if not self.restored:
				self.img.save_images()
			self.img.close()

	def on_socket_open(self, sk, uname):
		self.data_sk = sk
		logging.info("Data socket (%s) accepted", uname)

	def rpc_setup(self, htype_id):
		logging.info("Setting up service side %s", htype_id)
		self.img = images.phaul_images("rst")
		self.criu = criu_api.criu_conn(self.data_sk)
		self.htype = p_haul_type.get_dst(htype_id)

	def rpc_set_options(self, opts):
		self.criu.verbose(opts["verbose"])
		self.img.set_options(opts)
		self.htype.set_options(opts)

	def start_page_server(self):
		logging.info("Starting page server for iter %d", self.dump_iter)

		logging.info("\tSending criu rpc req")
		req = criu_req.make_page_server_req(self.htype, self.img, self.criu)
		resp = self.criu.send_req(req)
		if not resp.success:
			raise Exception("Failed to start page server")

		logging.info("\tPage server started at %d", resp.ps.pid)

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
		logging.info("Checking cpuinfo")
		req = criu_req.make_cpuinfo_check_req(self.htype, self.img)
		resp = self.criu.send_req(req)
		logging.info("\t`- %s", resp.success)
		return resp.success

	def rpc_restore_from_images(self):
		logging.info("Restoring from images")
		self.htype.put_meta_images(self.img.image_dir())
		self.htype.final_restore(self.img, self.criu)
		logging.info("Restore succeeded")
		self.restored = True

	def rpc_restore_time(self):
		stats = criu_api.criu_get_rstats(self.img)
		return stats.restore_time
