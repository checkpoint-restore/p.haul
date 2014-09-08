import os

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
