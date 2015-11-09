#
# Shared FS hauler (noop)
#

import logging


class p_haul_fs:
	def __init__(self):
		logging.info("Initilized shared FS hauler")

	def set_options(self, opts):
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
