#
# OpenVZ containers hauler module
#

import os
import p_haul_vz

name = "ovz"
vzpid_dir = "/var/lib/vzctl/vepid/"

class p_haul_type(p_haul_vz.p_haul_type):
	def __init__(self, ctid):
		p_haul_vz.p_haul_type.__init__(self, ctid)

	def root_task_pid(self):
		with open(os.path.join(vzpid_dir, self._ctid)) as pf:
			pid = pf.read()
			return int(pid)
