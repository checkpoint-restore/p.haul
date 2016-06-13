#
# CRIU requests creation and initialization helper methods
#

import pycriu.rpc


def _build_names(name_strings):
	names = {}
	for key, value in name_strings.items():
		if hasattr(pycriu.rpc, key):
			names[getattr(pycriu.rpc, key)] = value
	return names


_name_strings = {
	"DUMP": "dump",
	"PRE_DUMP": "pre_dump",
	"PAGE_SERVER": "page_server",
	"RESTORE": "restore",
	"CPUINFO_DUMP": "cpuinfo-dump",
	"CPUINFO_CHECK": "cpuinfo-check",
	"FEATURE_CHECK": "feature-check",
}

_names = _build_names(_name_strings)


def get_name(req_type):
	"""Return printable request name"""
	return _names[req_type]


def _make_req(typ, htype = None):
	"""Prepare generic criu request"""
	req = pycriu.rpc.criu_req()
	req.type = typ
	if htype:
		htype.adjust_criu_req(req)
	return req


def make_cpuinfo_dump_req(img):
	"""Prepare cpuinfo dump criu request (source side)"""
	req = _make_req(pycriu.rpc.CPUINFO_DUMP)
	req.opts.images_dir_fd = img.work_dir_fd()
	req.keep_open = True
	return req


def _make_common_dump_req(typ, pid, htype, img, connection, fs):
	"""Prepare common criu request for pre-dump or dump (source side)"""

	req = _make_req(typ, htype)
	req.opts.pid = pid
	req.opts.ps.fd = connection.mem_sk_fileno()

	req.opts.images_dir_fd = img.image_dir_fd()
	req.opts.work_dir_fd = img.work_dir_fd()
	p_img = img.prev_image_dir()
	if p_img:
		req.opts.parent_img = p_img
	if not fs.persistent_inodes():
		req.opts.force_irmap = True

	return req


def make_predump_req(pid, htype, img, connection, fs):
	"""Prepare pre-dump criu request (source side)"""
	return _make_common_dump_req(
		pycriu.rpc.PRE_DUMP, pid, htype, img, connection, fs)


def make_dump_req(pid, htype, img, connection, fs):
	"""Prepare dump criu request (source side)"""
	req = _make_common_dump_req(
		pycriu.rpc.DUMP, pid, htype, img, connection, fs)
	req.opts.notify_scripts = True
	req.opts.file_locks = True
	req.opts.evasive_devices = True
	req.opts.link_remap = True
	if htype.can_migrate_tcp():
		req.opts.tcp_established = True
	return req


def make_page_server_req(img, connection):
	"""Prepare page server criu request (destination side)"""

	req = _make_req(pycriu.rpc.PAGE_SERVER)
	req.keep_open = True
	req.opts.ps.fd = connection.mem_sk_fileno()
	req.opts.images_dir_fd = img.image_dir_fd()
	req.opts.work_dir_fd = img.work_dir_fd()

	p_img = img.prev_image_dir()
	if p_img:
		req.opts.parent_img = p_img

	return req


def make_cpuinfo_check_req(img):
	"""Prepare cpuinfo check criu request (destination side)"""
	req = _make_req(pycriu.rpc.CPUINFO_CHECK)
	req.keep_open = True
	req.opts.images_dir_fd = img.work_dir_fd()
	return req


def make_restore_req(htype, img, nroot):
	"""Prepare restore criu request (destination side)"""

	req = _make_req(pycriu.rpc.RESTORE, htype)
	req.opts.images_dir_fd = img.image_dir_fd()
	req.opts.work_dir_fd = img.work_dir_fd()
	req.opts.notify_scripts = True

	if htype.can_migrate_tcp():
		req.opts.tcp_established = True

	for veth in htype.veths():
		req.opts.veths.add(if_in = veth.name, if_out = veth.pair)

	if nroot:
		req.opts.root = nroot

	return req


def make_dirty_tracking_req(img):
	"""Check if dirty memory tracking is supported."""
	req = _make_req(pycriu.rpc.FEATURE_CHECK)
	req.features.mem_track = True
	req.keep_open = True
	req.opts.images_dir_fd = img.work_dir_fd()
	return req
