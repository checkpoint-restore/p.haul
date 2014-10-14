import os
import fcntl
import errno

class net_dev:
	def init(self):
		self.name = None
		self.pair = None
		self.link = None

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
	print "\t\tUpping %s" % ifname
	os.system("ip link set %s up" % ifname)

def ifdown(ifname):
	print "\t\tDowning %s" % ifname
	os.system("ip link set %s down" % ifname)

def bridge_add(ifname, brname):
	print "\t\tAdd %s to %s" % (ifname, brname)
	os.system("brctl addif %s %s" % (brname, ifname))

def set_cloexec(sk):
	fd = sk.fileno()
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
