# Copyright (C) 2015 Red Hat Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import web
import tempfile
import socket
import glob
import os
import json
import base64
import tarfile
from pycriu import rpc as criu


class _DRBase:
    CRIU_ADDR = "/var/run/criu-service.socket"
    tempdir = ""

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            self.sock.connect(self.CRIU_ADDR)
        except socket.error as e:
            result = {"succeeded": False, "why": e.strerror}
            raise web.internalerror(json.dumps(result, separators=",:"))

    def transaction(self, req):
        self.sock.send(req.SerializeToString())

        resp = criu.criu_resp()
        resp.ParseFromString(self.sock.recv(1024))

        if not resp.success:
            if resp.cr_errno:
                why = os.strerror(resp.cr_errno)
            else:
                why = "criu.log:\n" + "\n".join(line for line in open(
                    self.tempdir + "/criu.log"))

            result = result = {"succeeded": False, "why": why}
            raise web.internalerror(json.dumps(result, separators=",:"))

        return resp


class Dump(_DRBase):
    """
        This class dumps a process using CRIU when it receives an HTTP POST.
    """

    def POST(self):
        """
            Attempt to dump a process, where the PID is given in the URL
            parameter "pid".
        """

        web.header("Content-Type", "application/json")
        web.header("Access-Control-Allow-Origin", "*")
        pid = web.input().get("pid")

        if not pid or not pid.isnumeric():
            result = {"succeeded": False, "why": "No PID specified"}
            raise web.badrequest(json.dumps(result, separators=",:"))

        self.connect()

        self.tempdir = tempfile.mkdtemp()

        # Send a request to dump the specified process
        req = criu.criu_req()
        req.type = criu.DUMP
        req.opts.pid = int(pid)
        req.opts.shell_job = False
        req.opts.manage_cgroups = True
        req.opts.images_dir_fd = os.open(self.tempdir, os.O_DIRECTORY)

        resp = self.transaction(req)

        # Create a tar of all of the images and send it base64-encoded back to
        # the client.  This is okay for a small demo, but obviously a real
        # application would probably not be this wasteful with resources.
        temptar = tempfile.mktemp()

        with tarfile.open(temptar, "w:gz") as tar:
            for f in os.listdir(self.tempdir):
                tar.add(self.tempdir + "/" + f)
            tar.close()

        with open(temptar, "r") as tar:
            data = base64.b64encode(tar.read())

        return json.dumps({"succeeded": True, "data": data,
                          "dir": self.tempdir}, separators=",:")


class Restore(_DRBase):
    """
        This class restores a process using CRIU when it receives an HTTP POST.
    """

    def POST(self):
        """
            Attempt to restore a process, where the directory where the
            proccess images are is given in the URL parameter "dir".
        """

        web.header("Content-Type", "application/json")
        web.header("Access-Control-Allow-Origin", "*")

        if "data" not in web.input():
            result = {"succeeded": False, "why": "No image data provided"}
            raise web.badrequest(json.dumps(result, separators=",:"))

        if "dir" not in web.input():
            result = {"succeeded": False, "why": "No image directory provided"}
            raise web.badrequest(json.dumps(result, separators=",:"))

        # Extract the images from the base64-encoding tarball.
        temptar = tempfile.mktemp()
        self.tempdir = web.input()["dir"]

        print self.tempdir

        with open(temptar, "w") as tar:
            tar.write(base64.b64decode(web.input()["data"]))

        with tarfile.open(temptar, "r:gz") as tar:
            tar.list()
            tar.extractall("/")

        try:
            dir_fd = os.open(self.tempdir, os.O_DIRECTORY)
        except OSError as e:
            result = {"succeeded": False, "why": e.strerror}
            raise web.badrequest(json.dumps(result, separators=",:"))

        self.connect()

        # Send a request to restore the specified process
        req = criu.criu_req()
        req.type = criu.RESTORE
        req.opts.shell_job = False
        req.opts.manage_cgroups = True
        req.opts.images_dir_fd = dir_fd

        resp = self.transaction(req)
        return json.dumps({"succeeded": True}, separators=",:")
