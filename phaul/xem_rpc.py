#
# RPC server implementation
#

import logging
import select
import socket
import threading
import traceback

rpc_sk_buf = 16384

RPC_CMD = 1
RPC_CALL = 2

RPC_RESP = 1
RPC_EXC = 2


class _rpc_server_sk(object):
	def __init__(self, sk):
		self._sk = sk
		self._master = None

	def fileno(self):
		return self._sk.fileno()

	def work(self, mgr):
		raw_data = self._sk.recv(rpc_sk_buf)
		if not raw_data:
			mgr.remove_poll_item(self)
			if self._master:
				self._master.on_disconnect()
			return

		data = eval(raw_data)
		try:
			if data[0] == RPC_CALL:
				if not self._master:
					raise Exception("Proto seq error")

				res = getattr(self._master, "rpc_" + data[1])(*data[2])
			elif data[0] == RPC_CMD:
				res = getattr(self, data[1])(mgr, *data[2])
			else:
				raise Exception(("Proto typ error", data[0]))
		except Exception as e:
			traceback.print_exc()
			res = (RPC_EXC, e)
		else:
			res = (RPC_RESP, res)

		raw_data = repr(res)
		self._sk.send(raw_data)

	def init_rpc(self, mgr, args):
		self._master = mgr.make_master()
		self._master.on_connect(*args)


class _rpc_stop_fd(object):
	def __init__(self, fd):
		self._fd = fd

	def fileno(self):
		return self._fd.fileno()

	def work(self, mgr):
		mgr.stop()


class _rpc_server_manager(object):
	def __init__(self, srv_class, connection):
		self._srv_class = srv_class
		self._connection = connection
		self._poll_list = []
		self._alive = True

		self.add_poll_item(_rpc_server_sk(connection.rpc_sk))

	def add_poll_item(self, item):
		self._poll_list.append(item)

	def remove_poll_item(self, item):
		self._poll_list.remove(item)

	def make_master(self):
		return self._srv_class(self._connection)

	def stop(self):
		self._alive = False

	def loop(self, stop_fd):
		if stop_fd:
			self.add_poll_item(_rpc_stop_fd(stop_fd))

		while self._alive:
			r, w, x = select.select(self._poll_list, [], [])
			for sk in r:
				sk.work(self)

		logging.info("RPC Service stops")


class rpc_threaded_srv(threading.Thread):
	def __init__(self, srv_class, connection):
		threading.Thread.__init__(self)
		self._mgr = _rpc_server_manager(srv_class, connection)
		self._stop_fd = None

	def run(self):
		try:
			self._mgr.loop(self._stop_fd)
		except Exception:
			logging.exception("Exception in rpc_threaded_srv")

	def init_stop_fd(self):
		sks = socket.socketpair()
		self._stop_fd = sks[0]
		return sks[1]
