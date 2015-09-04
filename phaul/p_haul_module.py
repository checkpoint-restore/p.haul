#
# Generic functionality for p.haul modules
#

import pycriu.rpc
import criu_req

def final_restore(htype, img, connection):
	"""Perform final restore"""

	nroot = htype.mount()
	if nroot:
		print "Restore root set to %s" % nroot

	req = criu_req.make_restore_req(htype, img, nroot)
	resp = connection.send_req(req)
	while True:
		if resp.type == pycriu.rpc.NOTIFY:
			print "\t\tNotify (%s.%d)" % (resp.notify.script, resp.notify.pid)
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
