#
# CGroups manipulations for p.haul.
#
# FIXME Isn't it nicer to do it via libcgroup?
#

def dump_hier(pid, img):
	print "\tSave CG for %d into %s" % (pid, img)
	fd = open(img, "w")
	fd.close()

def restore_hier(pid, img):
	print "\tCreate hier for %d from %s" % (pid, img)
	pass
