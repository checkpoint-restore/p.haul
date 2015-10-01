p.haul web-gui mode
======

The code in the webgui and webgui/static directories is based on

 https://github.com/ThomasJClark/criu-gui-demo

To use p.haul in web-gui mode the p.haul-wrap script has to be started
on two hosts in web-gui mode:

* host01# ./p.haul-wrap service --web-gui
* host02# ./p.haul-wrap service --web-gui --web-partner host01

This way host02 will register itself with host01 and both hosts
will offer a web-interface at port 8080:

 http://host01:8080/

It it now possible to drag and drop a process from one host to another
which will trigger a p.haul controlled process migration in the
background.

To use p.haul in webgui mode the following additional python modules
are required: python-flask and python-psutil

The following is the content from the original README.md

CRIU GUI Demo (outdated)
======

A web-based demonstration of process migration with CRIU.

This demo requires criu, python 2.7, python-webpy, python-psutil, and python-criu to run.

To run the demo:

1. Edit the "targetData" object in static/criugui.js to point to at least two machines (ideally this shouldn't be hardcoded)
2. Make sure the CRIU RPC service is started with `sudo systemctl start criu.socket`.
3. Run `./criugui.py` on **both** machines.
4. Go to http://localhost:8080/ (assuming localhost is one of the machines)

![screenshot](https://cloud.githubusercontent.com/assets/3964980/9047457/168f7d20-3a00-11e5-9ae3-50cb82206aa3.png)

You can click and drag inside each of the panels to pan over the process trees, hover over a process name to see more information about it, and drag and drop a process from one panel to another to attempt to migrate it.  The results of the migration will show up in an alert box on the page.
