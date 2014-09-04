#
# CRIU API
# Includes class to work with CRIU service and helpers
#

import socket
import struct
import os
import subprocess
import rpc_pb2 as cr_rpc
import stats_pb2 as crs

criu_binary = "/root/criu/criu"

req_types = {
	cr_rpc.DUMP: "dump",
	cr_rpc.PRE_DUMP: "pre_dump",
	cr_rpc.PAGE_SERVER: "page_server",
	cr_rpc.RESTORE: "restore"
}

def_verb = 2

#
# Connection to CRIU service
#

class criu_conn:
	def __init__(self, mem_sk):
		self._iter = 0
		self.verb = def_verb
		css = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
		self.__swrk = subprocess.Popen([criu_binary, "swrk", "0"],
				stdin = css[0].fileno(), stdout = mem_sk.fileno(),
				stderr = None, close_fds = True)
		mem_sk.set_criu_fileno(1)
		css[0].close()
		self.__cs = css[1]

	def close(self):
		self.__cs.close()
		self.__swrk.wait()

	def verbose(self, level):
		self.verb = level

	def send_req(self, req, with_resp = True):
		req.opts.log_level = self.verb
		req.opts.log_file = "criu_%s.%d.log" % (req_types[req.type], self._iter)
		self.__cs.send(req.SerializeToString())
		self._iter += 1
		if with_resp:
			return self.recv_resp()

	def recv_resp(self):
		resp = cr_rpc.criu_resp()
		resp.ParseFromString(self.__cs.recv(1024))
		return resp

	def ack_notify(self, success = True):
		req = cr_rpc.criu_req()
		req.type = cr_rpc.NOTIFY
		req.notify_success = True
		self.__cs.send(req.SerializeToString())

#
# Helper to read CRIU-generated statistics
#

CRIU_STATS_MAGIC = 0x57093306

def criu_get_stats(img, file_name):
	s = struct.Struct("I I")
	f = open(os.path.join(img.work_dir(), file_name))
	#
	# Stats file is 4 butes of magic, then 4 bytes with
	# stats packet size
	#
	v = s.unpack(f.read(s.size))
	if v[0] != CRIU_STATS_MAGIC:
		raise Exception("Magic is %x, expect %x" % (v[0], CRIU_STATS_MAGIC))

	stats = crs.stats_entry()
	stats.ParseFromString(f.read(v[1]))

	return stats

def criu_get_dstats(img):
	stats = criu_get_stats(img, "stats-dump")
	return stats.dump

def criu_get_rstats(img):
	stats = criu_get_stats(img, "stats-restore")
	return stats.restore
