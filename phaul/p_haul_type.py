#
# Haulers' type selector
# Types (htypes) are classes, that help hauling processes.
# See p_haul_pid for comments of how a class should look like.
#

import logging
import p_haul_vz
import p_haul_pid
import p_haul_lxc

haul_types = {
	p_haul_vz.name: p_haul_vz,
	p_haul_pid.name: p_haul_pid,
	p_haul_lxc.name: p_haul_lxc,
}

def __get(id):
	if haul_types.has_key(id[0]):
		h_type = haul_types[id[0]]
		return h_type.p_haul_type(id[1])
	else:
		logging.info("Unknown type. Try one of %s", str(haul_types.keys()))
		return None

def get_src(id):
	ht = __get(id)
	ht.init_src()
	return ht

def get_dst(id):
	ht = __get(id)
	ht.init_dst()
	return ht
