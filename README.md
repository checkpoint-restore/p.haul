p.haul
======

Process HAULer -- a tool to live-migrate containers and processes

The live-migration idea is quite simple. To live migrate a task
one needs to

* stop it and save its state into image file(s)
* make images available on the remote host
* recreate task on it from the images

This is what p.haul does. It heavily uses CRIU (http://criu.org)
to do state dump and restore. Task's stopped time is decreased
using the CRIU's pre-dump action.

Get p.haul ready
=======

1. Install criu or put criu binary location to $PATH.

2. Install protobuf-compiler and python-protobuf packages.

3. Get the sources and run:

$make

This will generate rpc_pb2 and stats_pb2 python modules
from rpc.proto and stats.proto.

For more information read the P.Haul-related pages on the CRIU
wiki (http://criu.org/Category:P.Haul).
