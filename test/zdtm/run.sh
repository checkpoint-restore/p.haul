#!/bin/bash
set -x
CRIU_TESTS="../../../criu/test/zdtm/live/static"

make ct_init
if ! ./ct_init ct.log init.pid ./ct_init.py ${CRIU_TESTS} tests; then
	echo "Start FAIL"
	exit 1
fi

# Add migration here

PID=$(cat init.pid)
kill -TERM ${PID}
while kill -0 ${PID}; do
	echo "Waiting to die"
	sleep ".1"
done

tail -n1 ct.log
