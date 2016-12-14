#
# P.HAUL code, that helps on the target node (rpyc service)
#

import distutils.version
import logging

import criu_api
import criu_req
import htype
import images
import iters


class phaul_service(object):
	def __init__(self, connection):
		self.connection = connection
		self.htype = None
		self.__fs_receiver = None
		self.criu_connection = None
		self.img = None
		self.__mode = iters.MIGRATION_MODE_LIVE
		self.dump_iter_index = 0
		self.restored = False

	def on_connect(self):
		logging.info("Connected")

	def on_disconnect(self):
		logging.info("Disconnected")
		if self.criu_connection:
			self.criu_connection.close()

		if self.htype and not self.restored:
			if iters.is_live_mode(self.__mode):
				self.htype.umount()
			elif iters.is_restart_mode(self.__mode):
				self.htype.stop(True)

		if self.__fs_receiver:
			self.__fs_receiver.stop_receive()

		if self.img:
			logging.info("Closing images")
			if not self.restored:
				self.img.save_images()
			self.img.close()

	def rpc_setup(self, htype_id, mode):

		logging.info("Setting up service side %s", htype_id)
		self.__mode = mode

		self.htype = htype.get_dst(htype_id)

		self.__fs_receiver = self.htype.get_fs_receiver(self.connection.fdfs)
		if self.__fs_receiver:
			self.__fs_receiver.start_receive()

		if iters.is_live_mode(self.__mode):
			self.img = images.phaul_images("rst")
			self.criu_connection = criu_api.criu_conn(self.connection.mem_sk)

	def rpc_set_options(self, opts):
		self.htype.set_options(opts)
		if self.criu_connection:
			self.criu_connection.set_options(opts)
		if self.img:
			self.img.set_options(opts)

	def start_page_server(self):
		logging.info("Starting page server for iter %d", self.dump_iter_index)

		logging.info("\tSending criu rpc req")
		req = criu_req.make_page_server_req(self.img, self.criu_connection)
		resp = self.criu_connection.send_req(req)
		if not resp.success:
			raise Exception("Failed to start page server")

		logging.info("\tPage server started at %d", resp.ps.pid)

	def rpc_start_iter(self, need_page_server):
		self.dump_iter_index += 1
		self.img.new_image_dir()
		if need_page_server:
			self.start_page_server()

	def rpc_end_iter(self):
		pass

	def rpc_start_accept_images(self, dir_id):
		self.img.start_accept_images(dir_id, self.connection.mem_sk)

	def rpc_stop_accept_images(self):
		self.img.stop_accept_images()

	def rpc_check_cpuinfo(self):
		logging.info("Checking cpuinfo")
		req = criu_req.make_cpuinfo_check_req(self.img)
		resp = self.criu_connection.send_req(req)
		logging.info("\t`- %s", resp.success)
		return resp.success

	def rpc_check_criu_version(self, source_version):
		logging.info("Checking criu version")
		target_version = criu_api.get_criu_version()
		if not target_version:
			logging.info("\t`- Can't get criu version")
			return False
		lsource_version = distutils.version.LooseVersion(source_version)
		ltarget_version = distutils.version.LooseVersion(target_version)
		result = lsource_version <= ltarget_version
		logging.info("\t`- %s -> %s", source_version, target_version)
		logging.info("\t`- %s", result)
		return result

	def rpc_restore_from_images(self):
		logging.info("Restoring from images")
		self.htype.put_meta_images(self.img.image_dir())
		self.htype.final_restore(self.img, self.criu_connection)
		logging.info("Restore succeeded")
		self.restored = True

	def rpc_restore_time(self):
		stats = criu_api.criu_get_rstats(self.img)
		return stats.restore_time

	def rpc_start_htype(self):
		logging.info("Starting")
		self.htype.start()
		logging.info("Start succeeded")
		self.restored = True

	def rpc_migration_complete(self, src_data):
		self.htype.target_cleanup(src_data)
