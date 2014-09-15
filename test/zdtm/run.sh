#!/bin/bash
set -x
WDIR="$(pwd)/wdir"
CRIU_TESTS="../../../criu/test/zdtm/live/static"

rm -rf "$WDIR"
mkdir "$WDIR"

make ct_init
if ! ./ct_init "${WDIR}/ct.log" "${WDIR}/init.pid" ./ct_init.py ${CRIU_TESTS} tests; then
	echo "Start FAIL"
	exit 1
fi

PID=$(cat "${WDIR}/init.pid")
echo "Tests started at ${PID}"

echo "Start phaul service"
../../p.haul-service > "${WDIR}/ph-srv.log" 2>&1 &
PHSPID=$!

echo "Migrating"
if ! ../../p.haul pid ${PID} "127.0.0.1" -v=4 --keep-images --dst-rpid "${WDIR}/init2.pid" --img-path "${WDIR}"; then
	echo "Migration failed"
	kill -TERM ${PID}
	kill -TERM ${PHSPID}
	exit 1
fi

PID=$(cat "${WDIR}/init2.pid")

echo "Checking results, new pid ${PID}"
kill -TERM ${PID}
while kill -0 ${PID}; do
	echo "Waiting to die"
	sleep ".1"
done
kill -TERM ${PHSPID}

if tail -n1 "${WDIR}/ct.log" | fgrep PASS; then
	rm -rf "${WDIR}"
	exit 0
else
	echo "FAIL"
	exit 1
fi
