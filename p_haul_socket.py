import socket
import threading

ph_service_port = 18862

# Keeps accepted sockets with addr:port key
# The sk.peer_name() reports the peer's key
# The get_by_name()
#
# Synchronization note -- docs say, that dicts
# are thread-safe in terms of add/del/read won't
# corrupt the dictionary. Assuming I undersand
# this correctly, there's no any locks around
# this one. The socket connection process would
# look like this:
#
#  clnt                         srv
#                               start_listener()
#  sk = create(srv)
#  srv.pick_up(sk.name()) - - > sk = get_by_name(name)
#
#  < at this point clnt.sk and src.sk are connected >
#
ph_sockets = {}

class ph_socket:
	def __init__(self, sock = None):
		self._sk = sock
		self._hash_key = None

	def name(self):
		return self._sk.getsockname()

	def fileno(self):
		return self._sk.fileno()

	def criu_fileno(self):
		return self._criu_fileno

	def set_criu_fileno(self, val):
		self._criu_fileno = val

	def close(self):
		if self._sk:
			self._sk.close()
		if self._hash_key:
			print "Removing socket", self._hash_key
			ph_socket.pop(self._hash_key)

	# Private to local module methods

	def connect_to(self, tgt_host):
		if self._sk:
			self._sk.close()

		self._sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self._sk.connect((tgt_host, ph_service_port))

	def hash(self, key):
		self._hash_key = key
		ph_sockets[key] = self
		print "Hashing socket", key

class ph_socket_listener(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
		lsk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		lsk.bind(("0.0.0.0", ph_service_port))
		lsk.listen(4)

		self.lsk = lsk

	def run(self):
		while True:
			clnt, addr = self.lsk.accept()
			sk = ph_socket(clnt)
			sk.hash(addr)

			print "Accepted connection from", addr

def start_listener():
	lt = ph_socket_listener()
	lt.start()
	print "Listener started"

def create(tgt_host):
	sk = ph_socket()
	sk.connect_to(tgt_host)
	print "Connected ph socket to %s" % tgt_host
	return sk

def get_by_name(name):
	if ph_sockets.has_key(name):
		return ph_sockets[name]

	print "Missing socket", name
	return None
