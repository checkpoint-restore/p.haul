#!/bin/bash

exit_cleanup () {
    if [ "x${LOCAL_PHS_PID}" != "x" ]; then
        kill -TERM ${LOCAL_PHS_PID}
    fi
    return 0
}

set -x
CRIU_PATH="../../../criu/"
CRIU_TESTS="${CRIU_PATH}/test/zdtm/"
WDIR="$(pwd)/wdir"
PH=$(realpath ../../p.haul)
PHS=$(realpath ../../p.haul-service)
PHWRAP=$(realpath ../../p.haul-wrap)
PHSSH=$(realpath ../../p.haul-ssh)

# setup EXIT trap
trap exit_cleanup EXIT

# process command line options
while [ "${#}" -gt 0 ]; do
    case $1 in
    "--local")
        LOCAL_PHS="true"
        ;;
    esac
    shift
done

rm -rf "$WDIR"
mkdir "$WDIR"

# run local p.haul server in background if --local option specified
if [ "x${LOCAL_PHS}" == "xtrue" ]; then
    echo "Run local p.haul service"
    ${PHWRAP} service &> "/tmp/phs.log" &
    if [ ${?} -ne 0 ]; then
        echo "Can't run local p.haul service"
        exit 1
    fi
    LOCAL_PHS_PID=$!
fi

make ct_init
if ! ./ct_init "${WDIR}/ct.log" "${WDIR}/init.pid" ./ct_init.py ${CRIU_TESTS} tests; then
    echo "Start FAIL"
    exit 1
fi

PID=$(cat "${WDIR}/init.pid")
echo "Tests started at ${PID}"

export PATH="${PATH}:${CRIU_PATH}"
which criu

echo "Migrating"
if [ "x${LOCAL_PHS}" == "xtrue" ]; then
    ${PHWRAP} client "127.0.0.1" pid ${PID} -v=4 --keep-images \
        --dst-rpid "${WDIR}/init2.pid" --img-path "${WDIR}"
else
    ${PHSSH} --ssh-ph-exec ${PH} --ssh-ph-wrap-exec ${PHWRAP} \
        --ssh-phs-exec ${PHS} --ssh-phs-wrap-exec ${PHWRAP} \
        "127.0.0.1" pid ${PID} -v=4 --keep-images \
        --dst-rpid "${WDIR}/init2.pid" --img-path "${WDIR}"
fi

if [ ${?} -ne 0 ]; then
    echo "Migration failed"
    kill -TERM ${PID}
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

if tail -n1 "${WDIR}/ct.log" | fgrep PASS; then
    rm -rf "${WDIR}"
    exit 0
else
    echo "FAIL"
    exit 1
fi
