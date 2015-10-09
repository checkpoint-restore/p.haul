#
# P.HAUL code, that helps on the target node (rpyc service)
#

import logging
import xem_rpc
import images
import criu_api
import criu_req
import p_haul_type

class phaul_service:
	def __init__(self, mem_sk, fs_sk):
		self.criu_connection = None
		self._mem_sk = mem_sk
		self._fs_sk = fs_sk
		self.img = None
		self.htype = None
		self.dump_iter_index = 0
		self.restored = False

	def on_connect(self):
		logging.info("Connected")

	def on_disconnect(self):
		logging.info("Disconnected")
		if self.criu_connection:
			self.criu_connection.close()

		if self.htype and not self.restored:
			self.htype.umount()

		if self.img:
			logging.info("Closing images")
			if not self.restored:
				self.img.save_images()
			self.img.close()

	def rpc_setup(self, htype_id):
		logging.info("Setting up service side %s", htype_id)
		self.img = images.phaul_images("rst")
		self.criu_connection = criu_api.criu_conn(self._mem_sk)
		self.htype = p_haul_type.get_dst(htype_id)

	def rpc_set_options(self, opts):
		self.criu_connection.verbose(opts["verbose"])
		self.criu_connection.shell_job(opts["shell_job"])
		self.img.set_options(opts)
		self.htype.set_options(opts)

	def start_page_server(self):
		logging.info("Starting page server for iter %d", self.dump_iter_index)

		logging.info("\tSending criu rpc req")
		req = criu_req.make_page_server_req(self.htype, self.img,
			self.criu_connection)
		resp = self.criu_connection.send_req(req)
		if not resp.success:
			raise Exception("Failed to start page server")

		logging.info("\tPage server started at %d", resp.ps.pid)

	def rpc_start_iter(self):
		self.dump_iter_index += 1
		self.img.new_image_dir()
		self.start_page_server()

	def rpc_end_iter(self):
		pass

	def rpc_start_accept_images(self, dir_id):
		self.img.start_accept_images(dir_id, self._mem_sk)

	def rpc_stop_accept_images(self):
		self.img.stop_accept_images()

	def rpc_check_cpuinfo(self):
		logging.info("Checking cpuinfo")
		req = criu_req.make_cpuinfo_check_req(self.htype, self.img)
		resp = self.criu_connection.send_req(req)
		logging.info("\t`- %s", resp.success)
		return resp.success

	def rpc_restore_from_images(self):
		logging.info("Restoring from images")
		self.htype.put_meta_images(self.img.image_dir())
		self.htype.final_restore(self.img, self.criu_connection)
		logging.info("Restore succeeded")
		self.restored = True

	def rpc_restore_time(self):
		stats = criu_api.criu_get_rstats(self.img)
		return stats.restore_time
