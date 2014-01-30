#
# Haulers' type selector
# Types (htypes) are classes, that help hauling processes.
# See p_haul_pid for comments of how a class should look like.
#

import p_haul_ovz
import p_haul_pid

haul_types = {
	p_haul_ovz.name: p_haul_ovz,
	p_haul_pid.name: p_haul_pid
}

def get(id):
	if haul_types.has_key(id[0]):
		h_type = haul_types[id[0]]
		return h_type.p_haul_type(id[1])
	else:
		print "Unknown type. Try one of", haul_types.keys()
	 	return None
