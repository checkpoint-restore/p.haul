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

3. Install p.haul by running
	$ python setup.py install
   or just use it without installing.

For more information read the P.Haul-related pages on the CRIU
wiki (http://criu.org/Category:P.Haul).

How to contribute
=======

The p.haul patches should be sent to CRIU development mailing list
(https://openvz.org/mailman/listinfo/criu) with "p.haul" prefix.
Configure your local git repository using following command to
set subject prefix automatically:
* $ git config format.subjectprefix "PATCH p.haul"

Before sending patches please make sure your code formatted according to
project coding style (we use [PEP8](https://www.python.org/dev/peps/pep-0008/)
with some exceptions) and your changes don't introduce linter warnings.

How to run flake8 linter to verify p.haul:
* $ yum install python-setuptools
* $ easy_install pip
* $ pip install flake8
* $ make lint

BUGs
======

All BUGs are to be reported on the criu@openvz.org mailing list.
To [un]subscribe goto http://lists.openvz.org/mailman/listinfo/criu)
