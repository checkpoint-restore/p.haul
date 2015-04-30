#
# CGroups manipulations for p.haul.
#
# FIXME Isn't it nicer to do it via libcgroup?
#

import os

cg_root_dir = "/sys/fs/cgroup"
cg_tasks_file = "tasks"

def cg_line_parse(ln):
	items = ln.split(":")
	#
	# If two controllers are merged tigether, we see
	# their names comma-separated in proc. The problem
	# is that the respective directory name in sysfsis
	# (!) IS NOT THE SAME, controller names can go
	# reversed.
	#
	# That said, we just use the first name component,
	# in sysfs there would the respective symlink
	#
	cname = items[1].split(",")[0]
	cdir = items[2]

	return cname, cdir

def dump_hier(pid, img):
	print "\tSave CG for %d into %s" % (pid, img)
	fd = open(img, "w")
	cg = open("/proc/%d/cgroup" % pid)
	for ln in cg:
		cg_controller, cg_dir = cg_line_parse(ln)
		if not cg_controller.startswith("name="):
			fd.write("%s%s" % (cg_controller, cg_dir))

	cg.close()
	fd.close()

#
# The cpuset controller is unusable before at least one
# cpu and memory node is set there. For restore it's OK
# to copy parent masks into it, at the end we'll apply
# "real" CT config
#

def cpuset_copy_parent(path, c):
	c = "cpuset.%s" % c
	ppath = os.path.dirname(path)
	pfd = open(os.path.join(ppath, c))
	cfd = open(os.path.join(path, c), "w")
	cfd.write(pfd.read())
	cfd.close()
	pfd.close()

def cpuset_allow_all(path):
	cpuset_copy_parent(path, "cpus")
	cpuset_copy_parent(path, "mems")

def restore_one_controller(pid, ln):
	cg_path = os.path.join(cg_root_dir, ln.strip())
	print "[%s]" % cg_path
	if not os.access(cg_path, os.F_OK):
		os.makedirs(cg_path)
	if ln.startswith("cpuset"):
		cpuset_allow_all(cg_path)

	tf = open(os.path.join(cg_path, cg_tasks_file), "w")
	tf.write("%d" % pid)
	tf.close()

def restore_hier(pid, img):
	print "\tCreate hier for %d from %s" % (pid, img)
	fd = open(img)
	for ln in fd:
		restore_one_controller(pid, ln)
	fd.close()
	pass
