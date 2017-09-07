#!/usr/bin/env python

# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com


import time
import json

from opsbro.log import cprint, logger

from opsbro.unixclient import request_errors
from opsbro.cli import get_opsbro_local


def do_exec(group='*', cmd='uname -a'):
    if cmd == '':
        logger.error('Missing command')
        return
    try:
        (code, r) = get_opsbro_local('/exec/%s?cmd=%s' % (group, cmd))
    except request_errors, exp:
        logger.error(exp)
        return
    print r
    cid = r
    print "Command group launch as cid", cid
    time.sleep(5)  # TODO: manage a real way to get the result..
    try:
        (code, r) = get_opsbro_local('/exec-get/%s' % cid)
    except request_errors, exp:
        logger.error(exp)
        return
    j = json.loads(r)
    
    res = j['res']
    for (uuid, e) in res.iteritems():
        node = e['node']
        nname = node['name']
        color = {'alive': 'green', 'dead': 'red', 'suspect': 'yellow', 'leave': 'cyan'}.get(node['state'], 'cyan')
        cprint(nname, color=color)
        cprint('Return code:', end='')
        color = {0: 'green', 1: 'yellow', 2: 'red'}.get(e['rc'], 'cyan')
        cprint(e['rc'], color=color)
        cprint('Output:', end='')
        cprint(e['output'].strip(), color=color)
        if e['err']:
            cprint('Error:', end='')
            cprint(e['err'].strip(), color='red')
        print ''


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
