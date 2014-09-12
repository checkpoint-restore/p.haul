#!/bin/bash
set -x
CRIU_TESTS="../../../criu/test/zdtm/live/static"

make ct_init
if ! ./ct_init ct.log init.pid ./ct_init.py ${CRIU_TESTS} tests; then
	echo "Start FAIL"
	exit 1
fi

PID=$(cat init.pid)
echo "Tests started at ${PID}"

echo "Start phaul service"
../../p.haul-service > ph-srv.log 2>&1 &
PHSPID=$!

echo "Migrating"
if ! ../../p.haul pid ${PID} "127.0.0.1" -v=4 --keep-images; then
	echo "Migration failed"
	kill -TERM ${PID}
	kill -TERM ${PHSPID}
	exit 1
fi

echo "Checking results"
kill -TERM ${PID}
while kill -0 ${PID}; do
	echo "Waiting to die"
	sleep ".1"
done
kill -TERM ${PHSPID}

tail -n1 ct.log
