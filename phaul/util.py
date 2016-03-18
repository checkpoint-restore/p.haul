import os
import fcntl
import errno
import logging
import socket


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

	def write(self, data):
		self.__sk.sendall(data)
		return len(data)


def discard_sk_input(sk):
	"""Read all data from socket and discard it

	Current helper function needed to workaround tarfile library bug that
	leads to ownerless garbage zero blocks in socket when tarfile constructed
	with socket as file object to transfer tarballs over network.
	"""
	try:
		while True:
			sk.recv(0x10000, socket.MSG_DONTWAIT)
	except socket.error as e:
		if e.errno != errno.EWOULDBLOCK:
			raise e


class net_dev:
	def __init__(self, name=None, pair=None, link=None):
		self.name = name
		self.pair = pair
		self.link = link


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
