#!/bin/bash
set -x
CRIU_PATH="../../../criu/"
CRIU_TESTS="${CRIU_PATH}/test/zdtm/"
WDIR="$(pwd)/wdir"

rm -rf "$WDIR"
mkdir "$WDIR"

make ct_init
if ! ./ct_init "${WDIR}/ct.log" "${WDIR}/init.pid" ./ct_init.py ${CRIU_TESTS} tests; then
	echo "Start FAIL"
	exit 1
fi

PID=$(cat "${WDIR}/init.pid")
echo "Tests started at ${PID}"

export PATH="${PATH}:${CRIU_PATH}"
which criu

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
WTM=1
while kill -0 ${PID}; do
	echo "Waiting to die"
	sleep ".${WTM}"
	[ $WTM -lt 9 ] && ((WTM++))
done
kill -TERM ${PHSPID}

if tail -n1 "${WDIR}/ct.log" | fgrep PASS; then
	rm -rf "${WDIR}"
	exit 0
else
	echo "FAIL"
	exit 1
fi
