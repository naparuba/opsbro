#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

from __future__ import print_function
import time
import sys
import base64

from opsbro.log import cprint, logger
from opsbro.unixclient import get_request_errors
from opsbro.cli import wait_for_agent_started, get_opsbro_json
from opsbro.util import unicode_to_bytes, bytes_to_unicode


def do_exec(group='*', cmd='uname -a'):
    if cmd == '':
        logger.error('Missing command')
        return
    # The information is available only if the agent is started
    wait_for_agent_started(visual_wait=True)
    
    cmd_64 = bytes_to_unicode(base64.b64encode(unicode_to_bytes(cmd)))
    try:
        r = get_opsbro_json('/exec/%s?cmd=%s' % (group, cmd_64))
    except get_request_errors() as exp:
        cprint('ERROR: cannot launch the command: %s' % exp, color='red')
        sys.exit(2)
    
    cid = r
    print("Command group launch as cid", cid)
    time.sleep(5)  # TODO: manage a real way to get the result..
    try:
        r = get_opsbro_json('/exec-get/%s' % cid)
    except get_request_errors() as exp:
        cprint('ERROR: cannot get execution results: %s' % exp, color='red')
        sys.exit(2)
    
    res = r['res']
    print('Launched at: %s' % res)
    
    for (uuid, e) in res.items():
        node = e['node']
        nname = node['name']
        color = {'alive': 'green', 'dead': 'red', 'suspect': 'yellow', 'leave': 'cyan'}.get(node['state'], 'cyan')
        cprint(nname, color=color)
        cprint('Return code for [%s]:' % e['cmd'], end='')
        color = {0: 'green', 1: 'yellow', 2: 'red'}.get(e['rc'], 'cyan')
        cprint(e['rc'], color=color)
        cprint('Output:', end='')
        cprint(e['output'].strip(), color=color)
        if e['err']:
            cprint('Error:', end='')
            cprint(e['err'].strip(), color='red')
        cprint('')


exports = {
    do_exec: {
        'keywords'   : ['executors', 'exec'],
        'args'       : [
            {'name': 'group', 'default': '', 'description': 'Name of the node group to execute command on'},
            {'name': 'cmd', 'default': 'uname -a', 'description': 'Command to run on the nodes'},
        ],
        'description': 'Execute a command (default to uname -a) on a group of node of the good group (default to all)'
    },
    
}
