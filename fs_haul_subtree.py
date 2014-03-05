#
# FS haul driver, that copies the subtree from
# one node to another using rsync. It's used in
# legacy OpenVZ configurations.
#

class p_haul_fs:
	def __init__(self, subtree_path):
		print "Initialized subtree FS hauler (%s)" % subtree_path
		self.__root = subtree_path
		pass

	def start_migration(self):
		pass

	def next_iteration(self):
		pass

	def stop_migration(self):
		pass
