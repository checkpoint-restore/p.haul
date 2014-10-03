#
# CRIU API
# Includes class to work with CRIU service and helpers
#

import socket
import struct
import os
import util
import subprocess
import rpc_pb2 as cr_rpc
import stats_pb2 as crs

criu_binary = "criu"

req_types = {
	cr_rpc.DUMP: "dump",
	cr_rpc.PRE_DUMP: "pre_dump",
	cr_rpc.PAGE_SERVER: "page_server",
	cr_rpc.RESTORE: "restore",
	cr_rpc.CPUINFO_DUMP: "cpuinfo-dump",
	cr_rpc.CPUINFO_CHECK: "cpuinfo-check",
}

cpuinfo_img_name = "cpuinfo.img"

def_verb = 2

#
# Connection to CRIU service
#

class criu_conn:
	def __init__(self, mem_sk):
		self._iter = 0
		self.verb = def_verb
		css = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
		util.set_cloexec(css[1])
		print "`- Passing (ctl:%d, data:%d) pair to CRIU" % (css[0].fileno(), mem_sk.fileno())
		self._swrk = subprocess.Popen([criu_binary, "swrk", "%d" % css[0].fileno()])
		css[0].close()
		self._cs = css[1]
		self._last_req = -1
		self._mem_fd = mem_sk.fileno()

	def close(self):
		self._cs.close()
		self._swrk.wait()

	def mem_sk_fileno(self):
		return self._mem_fd

	def verbose(self, level):
		self.verb = level

	def _recv_resp(self):
		resp = cr_rpc.criu_resp()
		resp.ParseFromString(self._cs.recv(1024))
		if not resp.type in (cr_rpc.NOTIFY, self._last_req):
			raise Exception("CRIU RPC error (%d/%d)" % (resp.type, self._last_req))

		return resp

	def send_req(self, req):
		req.opts.log_level = self.verb
		req.opts.log_file = "criu_%s.%d.log" % (req_types[req.type], self._iter)
		self._cs.send(req.SerializeToString())
		self._iter += 1
		self._last_req = req.type

		return self._recv_resp()

	def ack_notify(self, success = True):
		req = cr_rpc.criu_req()
		req.type = cr_rpc.NOTIFY
		req.notify_success = True
		self._cs.send(req.SerializeToString())

		return self._recv_resp()

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
