import os
import fcntl
import errno
import logging

class fileobj_wrap:
	"""Helper class provides read/write interface for socket object

	Current helper class wrap recv/send socket methods in read/write interface.
	This functionality needed to workaround some problems of socket.makefile
	method for sockets constructed from numerical file descriptors passed
	through command line arguments.
	"""

	def __init__(self, sk):
		self.__sk = sk

	def read(self, size=0x10000):
		return self.__sk.recv(size)

	def write(self, str):
		self.__sk.send(str)

class net_dev:
	def __init__(self, name=None, pair=None, link=None):
		self.name = name
		self.pair = pair
		self.link = link

def path_to_fs(path):
	dev = os.stat(path)
	dev_str = "%d:%d" % (os.major(dev.st_dev), os.minor(dev.st_dev))
	mfd = open("/proc/self/mountinfo")
	for ln in mfd:
		ln_p = ln.split(None, 9)
		if dev_str == ln_p[2]:
			return ln_p[8]

	return None

def ifup(ifname):
	logging.info("\t\tUpping %s", ifname)
	os.system("ip link set %s up" % ifname)

def ifdown(ifname):
	logging.info("\t\tDowning %s", ifname)
	os.system("ip link set %s down" % ifname)

def bridge_add(ifname, brname):
	logging.info("\t\tAdd %s to %s", ifname, brname)
	os.system("brctl addif %s %s" % (brname, ifname))

def set_cloexec(sk):
	flags = fcntl.fcntl(sk, fcntl.F_GETFD)
	fcntl.fcntl(sk, fcntl.F_SETFD, flags | fcntl.FD_CLOEXEC)

def makedirs(dirpath):
	try:
		os.makedirs(dirpath)
	except OSError as er:
		if er.errno == errno.EEXIST and os.path.isdir(dirpath):
			pass
		else:
			raise
