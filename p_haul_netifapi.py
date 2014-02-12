#
# Various stuff to work with Linux network links
# FIXME -- rewrite this stuff using C-binding. Forking
# an IP tool is too heavy
#

import os

def ifup(ifname):
	print "\t\tUpping %s" % ifname
	os.system("ip link set %s up" % ifname)

def ifdown(ifname):
	print "\t\tDowning %s" % ifname
	os.system("ip link set %s down" % ifname)
