#
# Haulers' type selector
# Types (htypes) are classes, that help hauling processes.
# See p_haul_pid for comments of how a class should look like.
#

import importlib
import logging


__haul_modules = {
	"vz": "p_haul_vz",
	"pid": "p_haul_pid",
	"lxc": "p_haul_lxc",
	"docker": "p_haul_docker",
}


def get_haul_names():
	"""Return list of available haulers"""
	return __haul_modules.keys()


def add_hauler_args(hauler_name, parser):
	"""Add hauler specific command line arguments"""

	hauler_module = __get_module(hauler_name)
	add_args_func = getattr(hauler_module, "add_hauler_args", None)
	if add_args_func:
		add_args_func(parser)


def get_src(id):
	ht = __get(id)
	ht.init_src()
	return ht


def get_dst(id):
	ht = __get(id)
	ht.init_dst()
	return ht


def __get(id):
	hauler_name, haulee_id = id[0], id[1]
	if hauler_name not in __haul_modules:
		logging.error("Unknown type. Try one of %s", str(get_haul_names()))
		return None

	hauler_module = __get_module(hauler_name)
	logging.debug("%s hauler imported from %s", hauler_name,
				hauler_module.__file__)
	return hauler_module.p_haul_type(haulee_id)


def __get_module(hauler_name):
	"""Import specified haulers module relatively and return module object"""
	module_name = ".{0}".format(__haul_modules[hauler_name])
	module = importlib.import_module(module_name, __package__)
	return module
