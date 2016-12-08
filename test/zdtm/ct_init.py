#!/usr/bin/env python
import os
import signal
import sys

criu_tests_dir = sys.argv[1]
test_list = map(lambda x: x.strip(), open(sys.argv[2]).readlines())


def wup(foo, bar):
    pass

signal.signal(signal.SIGTERM, wup)


def getmlist():
    return [x.split()[4] for x in open("/proc/self/mountinfo").readlines()]


def try_umont(ml):
    fl = [x for x in ml if x not in ("/", "/proc")]
    for p in fl:
        print("Umounting [%s]" % p)
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
print("Me:", os.getpid(), os.getpgrp(), os.getsid(0))
print("Left:", ml)
print("Proc:", os.listdir("/proc"))

#
# From now on make's output will mess with
# python print-s. Flush them into logfile
# for easier reading
#
sys.stdout.flush()
sys.stderr.flush()

os.chdir(criu_tests_dir + "/live/")
os.system("make cleanout")
for tst in test_list:
    os.system("make -C %s %s.pid" % tuple(tst.rsplit("/", 1)))

os.write(3, "!")
os.close(3)
signal.pause()

for tst in test_list:
    # XXX: there's a make %test.out command, but
    # plain kill -TERM does _exactly_ the same and
    # is slightly faster
    os.kill(int(open("%s.pid" % tst).readline()), signal.SIGTERM)

while True:
    try:
        os.wait()
    except Exception:
        print("No more kids")
        break

flist = []
for tst in test_list:
    res = [x for x in open("%s.out" % tst).readlines() if x.endswith("PASS\n")]
    if not res:
        flist.append(tst)

if len(flist) != 0:
    print("Some tests failed:")
    print(flist)
    print("FAIL")
else:
    print("PASS")
