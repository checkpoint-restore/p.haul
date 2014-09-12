#!/bin/env python
import os
import sys
import signal

criu_tests_dir = sys.argv[1]
test_list = map(lambda x: x.strip(), open(sys.argv[2]).readlines())

def wup(foo, bar):
	pass

signal.signal(signal.SIGTERM, wup)

def getmlist():
	return map(lambda x: x.split()[4], open("/proc/self/mountinfo").readlines())

def try_umont(ml):
	fl = filter(lambda x: not x in ("/", "/proc"), ml)
	for p in fl:
		print "Umounting [%s]" % p
		os.system("umount -l %s >/dev/null 2>&1" % p)

def umount_all():
	at = 0
	while True:
		ml = getmlist()
		if len(ml) == 2 or at >= 8:
			return ml

		try_umont(ml)
		at += 1

ml = umount_all()
print "Me:", os.getpid(), os.getpgrp(), os.getsid(0)
print "Left:", ml
print "Proc:", os.listdir("/proc")

#
# From now on make's output will mess with
# python print-s. Flush them into logfile
# for easier reading
#
sys.stdout.flush()
sys.stderr.flush()

os.chdir(criu_tests_dir)
os.system("make cleanout")
for tst in test_list:
	os.system("make %s.pid" % tst)

os.write(3, "!")
os.close(3)
signal.pause()

for tst in test_list:
	os.kill(int(open("%s.pid" % tst).readline()), signal.SIGTERM)

while True:
	try:
		os.wait()
	except:
		print "No more kids"
		break

flist = []
for tst in test_list:
	res = filter(lambda x: x.endswith("PASS\n"), open("%s.out" % tst).readlines())
	if len(res) == 0:
		flist.append(tst)

if len(flist) != 0:
	print "Some tests failed:"
	print flist
	print "FAIL"
else:
	print "All tests PASS"
