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

import argparse
import flask
import json
import os
import requests
import socket
import sys

default_port = 8080
partner = "localhost"
myself = "localhost"
rpc_port = 12345

APP = flask.Flask(__name__)

# this handles /procs
import webgui.procs

@APP.after_request
def add_header(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@APP.route('/')
def index():
    return flask.redirect(flask.url_for('static', filename='index.html'))


@APP.route('/partners')
def partners():
    result = [{"name": "First Host (%s)" %
               myself, "address": "http://%s:8080" %
               myself}, {"name": "Second Host (%s)" %
                         partner, "address": "http://%s:8080" %
                         partner}]
    return flask.jsonify(results=result)


@APP.route('/register', methods=['POST'])
def register():
    global partner
    global myself

    myself = flask.request.form.get("partner")
    partner = flask.request.remote_addr
    return flask.jsonify({"your_ip": partner})


@APP.route('/migrate')
def migrate():
    """
        Attempt to migrate a process, where the PID is given in the URL
        parameter "pid".
    """

    pid = flask.request.args.get('pid')

    if not pid or not pid.isnumeric():
        return flask.jsonify({"succeeded": False, "why": "No PID specified"})

    dest_host = partner, rpc_port

    connection_sks = [None, None]

    for i in range(len(connection_sks)):
        connection_sks[i] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connection_sks[i].connect(dest_host)

    # Organize p.haul args
    target_args = ['./p.haul', 'pid', pid, '-v', '4', '-j']
    target_args.extend(["--to", partner,
                        "--fdrpc", str(connection_sks[0].fileno()),
                        "--fdmem", str(connection_sks[1].fileno())])

    # Call p.haul
    print "Exec p.haul: {0}".format(" ".join(target_args))
    os.system(" ".join(target_args))

    return flask.jsonify({"succeeded": True})


def start_web_gui(migration_partner, _rpc_port, _debug=False):
    global partner
    global myself
    global rpc_port
    rpc_port = _rpc_port
    partner = migration_partner
    if partner:
        try:
            myself = requests.post("http://%s:%d/register" %
                                   (partner, default_port),
                                   data={"partner": partner}
                                   ).json()['your_ip']
        except:
            pass
    APP.run(host='0.0.0.0', port=default_port, debug=_debug, threaded=True)
