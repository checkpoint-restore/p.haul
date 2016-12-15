#!/bin/bash

set -x
set -e

gcc "mem-touch.c" -o "mem-touch"
for f in $(ldd "mem-touch" | grep -P '^\s' | grep -v vdso | sed "s/.*=> //" | awk '{ print $1 }'); do
    cp "$f" .
done

rm -f "mem-touch-stop"
LD_LIBRARY_PATH=$(pwd) "./mem-touch" "mem-touch.log" "256m:64m:100000"
