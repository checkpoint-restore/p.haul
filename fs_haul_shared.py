#
# Shared FS hauler (noop)
#

class p_haul_fs:
	def __init__(self):
		print "Initilized shared FS hauler"
		pass

	def set_target_host(self, thost):
		pass

	def set_work_dir(self, wdir):
		pass

	def start_migration(self):
		pass

	def next_iteration(self):
		pass

	def stop_migration(self):
		pass

	# Inode numbers do not change on this FS
	# during migration
	def persistent_inodes(self):
		return True
