#
# Generic functionality for p.haul modules
#

import logging
import pycriu.rpc_pb2
import criu_req


def criu_predump(htype, pid, img, criu_connection, fs):
	logging.info("\tIssuing pre-dump command to service")
	req = criu_req.make_predump_req(pid, htype, img, criu_connection, fs)
	resp = criu_connection.send_req(req)
	if not resp.success:
		raise Exception("Pre-dump failed")


def criu_dump(htype, pid, img, criu_connection, fs):
	logging.info("\tIssuing dump command to service")
	req = criu_req.make_dump_req(pid, htype, img, criu_connection, fs)
	resp = criu_connection.send_req(req)
	while True:
		if resp.type != pycriu.rpc.NOTIFY:
			raise Exception("Dump failed")

		if resp.notify.script == "post-dump":
			#
			# Dump is effectively over. Now CRIU
			# waits for us to do whatever we want
			# and keeps the tasks frozen.
			#
			break

		elif resp.notify.script == "network-lock":
			htype.net_lock()
		elif resp.notify.script == "network-unlock":
			htype.net_unlock()

		logging.info("\t\tNotify (%s)", resp.notify.script)
		resp = criu_connection.ack_notify()


def criu_restore(htype, img, connection):
	"""Perform final restore"""

	nroot = htype.mount()
	if nroot:
		logging.info("Restore root set to %s", nroot)

	req = criu_req.make_restore_req(htype, img, nroot)
	resp = connection.send_req(req)
	while True:
		if resp.type == pycriu.rpc.NOTIFY:
			logging.info("\t\tNotify (%s.%d)", resp.notify.script, resp.notify.pid)
			if resp.notify.script == "setup-namespaces":
				#
				# At that point we have only one task
				# living in namespaces and waiting for
				# us to ACK the notify. Htype might want
				# to configure namespace (external net
				# devices) and cgroups
				#
				htype.prepare_ct(resp.notify.pid)
			elif resp.notify.script == "network-unlock":
				htype.net_unlock()
			elif resp.notify.script == "network-lock":
				raise Exception("Locking network on restore?")

			resp = connection.ack_notify()
			continue

		if not resp.success:
			raise Exception("Restore failed")
		break

	htype.restored(resp.restore.pid)
