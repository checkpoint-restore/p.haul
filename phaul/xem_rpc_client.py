#
# RPC client implementation
#

import logging
import xem_rpc


class _rpc_proxy_caller(object):
	def __init__(self, sk, typ, fname):
		self._rpc_sk = sk
		self._fn_typ = typ
		self._fn_name = fname

	def __call__(self, *args):
		call = (self._fn_typ, self._fn_name, args)
		raw_data = repr(call)
		self._rpc_sk.send(raw_data)
		raw_data = self._rpc_sk.recv(xem_rpc.rpc_sk_buf)
		resp = eval(raw_data)

		if resp[0] == xem_rpc.RPC_RESP:
			return resp[1]
		elif resp[0] == xem_rpc.RPC_EXC:
			logging.info("Remote exception")
			raise Exception(resp[1])
		else:
			raise Exception("Proto resp error")


class rpc_proxy(object):
	def __init__(self, sk, *args):
		self._rpc_sk = sk
		c = _rpc_proxy_caller(self._rpc_sk, xem_rpc.RPC_CMD, "init_rpc")
		c(args)

	def __getattr__(self, attr):
		return _rpc_proxy_caller(self._rpc_sk, xem_rpc.RPC_CALL, attr)
