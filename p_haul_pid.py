#
# Individual process hauler
#

name = "pid"

class p_haul_type:
	def __init__(self, id):
		self.pid = int(id)

	def id(self):
		return (name, "%d" % self.pid)

	def root_task_pid(self):
		return self.pid

	def prepare_fs(self):
		return None

	def unroll_fs(self):
		pass

	def get_meta_images(self):
		return []

	def put_meta_images(self, dir):
		pass
