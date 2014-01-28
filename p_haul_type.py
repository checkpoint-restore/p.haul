#
# Haulers' type selector
#

import p_haul_ovz
import p_haul_pid

haul_types = {
	p_haul_pid.name: p_haul_pid
}

def get(name, id):
	if haul_types.has_key(name):
		h_type = haul_types[name]
		return h_type.p_haul_type(id)
	else:
		print "Unknown type. Try one of", haul_types.keys()
	 	return None
