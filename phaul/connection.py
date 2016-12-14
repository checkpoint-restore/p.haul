#
# p.haul connection module contain logic needed to establish connection
# between p.haul and p.haul-service.
#

import logging
import socket
import util


class connection(object):
	"""p.haul connection

	Class encapsulate connections reqired for p.haul work, including rpc socket
	(socket for RPC calls), memory socket (socket for c/r images migration) and
	module specific definition of fs channel needed for disk migration.
	"""

	def __init__(self, rpc_sk, mem_sk, fdfs):
		self.rpc_sk = rpc_sk
		self.mem_sk = mem_sk
		self.fdfs = fdfs

	def close(self):
		self.rpc_sk.close()
		self.mem_sk.close()


def establish(fdrpc, fdmem, fdfs):
	"""Construct required socket objects from file descriptors

	Expect that each file descriptor represent socket opened in blocking mode
	with domain AF_INET and type SOCK_STREAM.
	"""

	logging.info(
		"Use existing connections, fdrpc=%d fdmem=%d fdfs=%s", fdrpc,
		fdmem, fdfs)

	# Create rpc socket
	rpc_sk = socket.fromfd(fdrpc, socket.AF_INET, socket.SOCK_STREAM)
	util.set_cloexec(rpc_sk)

	# Create memory socket
	mem_sk = socket.fromfd(fdmem, socket.AF_INET, socket.SOCK_STREAM)

	return connection(rpc_sk, mem_sk, fdfs)
