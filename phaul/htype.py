#
# Haulers' type selector
# Types (htypes) are classes, that help hauling processes.
# See p_haul_pid for comments of how a class should look like.
#

import logging
import importlib

__haul_modules = {
	"vz": "p_haul_vz",
	"pid": "p_haul_pid",
	"lxc": "p_haul_lxc",
}

def __get(id):
	hauler_name, haulee_id = id[0], id[1]
	if hauler_name not in __haul_modules:
		logging.error("Unknown type. Try one of %s", str(get_haul_names()))
		return None

	# Import specified haulers module relatively
	hauler_module_name = ".{0}".format(__haul_modules[hauler_name])
	hauler_module = importlib.import_module(hauler_module_name, __package__)
	logging.debug("%s hauler imported from %s", hauler_name,
		hauler_module.__file__)

	return hauler_module.p_haul_type(haulee_id)

def get_haul_names():
	"""Return list of available haulers"""
	return __haul_modules.keys()

def get_src(id):
	ht = __get(id)
	ht.init_src()
	return ht

def get_dst(id):
	ht = __get(id)
	ht.init_dst()
	return ht
