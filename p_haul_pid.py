#
# Individual process hauler
#

name = "pid"

class p_haul_type:
	def __init__(self, id):
		self.pid = int(id)


	#
	# Initialize itself for source node or destination one
	#
	def init_src(self):
		pass
	def init_dst(self):
		pass

	# Get tuple of name and id to construct the
	# same object on the remote host
	def id(self):
		return (name, "%d" % self.pid)

	# Report the pid of the root task of what we're
	# goung to migrate
	def root_task_pid(self):
		return self.pid

	# Prepare filesystem before restoring. Retrun
	# the new root, if required. 'None' will mean
	# that things will get restored in the current
	# mount namespace and w/o chroot
	def prepare_fs(self):
		return None

	# Roll back any changes done by prepare_fs
	def unroll_fs(self):
		pass

	# Get list of files which should be copied to
	# the destination node. The dir argument is where
	# temporary stuff can be put
	def get_meta_images(self, dir):
		return []

	# Take your files from dir and put in whatever
	# places are appropriate. Paths (relative) are
	# preserved.
	def put_meta_images(self, dir):
		pass

	# Things are started to get restored, only the
	# first task (with pid @pid) is created.
	def prepare_ct(self, pid):
		pass

	# Get list of veth pairs if any
	def veths(self):
		return []

	# Restoring done, the new top task has pid pid
	def restored(self, pid):
		pass

	# The task/container is no longer here -- clean
	# things up if required
	def clean_migrated(self):
		pass

	#
	# Lock and unlock networking
	#
	def net_lock(self):
		pass

	def net_unlock(self):
		pass
