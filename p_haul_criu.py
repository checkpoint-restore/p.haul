#
# CRIU API
# Includes class to work with CRIU service and helpers
#

import socket
import struct
import os
import rpc_pb2 as cr_rpc
import stats_pb2 as crs

criu_socket = "/var/run/criu_service.socket"
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
	def __init__(self):
		print "\tConnecting to CRIU service"
		self.cs = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
		self.cs.connect(criu_socket)
		self.verb = def_verb

	def verbose(self, level):
		self.verb = level

	def send_req(self, req, with_resp = True):
		req.opts.log_level = self.verb
		req.opts.log_file = "criu_%s.log" % req_types[req.type]
		self.cs.send(req.SerializeToString())
		if with_resp:
			return self.recv_resp()

	def recv_resp(self):
		resp = cr_rpc.criu_resp()
		resp.ParseFromString(self.cs.recv(1024))
		return resp

	def ack_notify(self):
		req = cr_rpc.criu_req()
		req.type = cr_rpc.NOTIFY
		req.notify_success = True
		self.cs.send(req.SerializeToString())

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
		print "Magic is %x, expect %x" % (magic, CRIU_STATS_MAGIC)
		raise 1

	stats = crs.stats_entry()
	stats.ParseFromString(f.read(v[1]))

	return stats

def criu_get_dstats(img):
	stats = criu_get_stats(img, "stats-dump")
	return stats.dump

def criu_get_rstats(img):
	stats = criu_get_stats(img, "stats-restore")
	return stats.restore
