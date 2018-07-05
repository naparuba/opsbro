#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com


import json
import time
import sys

from opsbro.cli import get_opsbro_local, print_info_title, print_2tab, get_opsbro_json
from opsbro.cli_display import print_element_breadcumb, print_h1, print_h2
from opsbro.characters import CHARACTERS
from opsbro.log import cprint, logger
from opsbro.unixclient import get_request_errors


def do_detect_list():
    try:
        (code, r) = get_opsbro_local('/agent/detectors')
    except get_request_errors() as exp:
        logger.error(exp)
        return
    
    try:
        d = json.loads(r)
    except ValueError as exp:  # bad json
        logger.error('Bad return from the server %s' % exp)
        return
    print_info_title('Detectors')
    logger.debug(str(d))
    e = []
    d = sorted(d, key=lambda i: i['name'])
    for i in d:
        # aligne name too
        name = '%-20s' % i['name'].split('/')[-1]
        groups = i['add_groups']
        # align pack level
        pack_level = '%-6s' % i['pack_level']
        # Aligne pack name
        pack_name = '%-10s' % i['pack_name']
        
        print_element_breadcumb(pack_name, pack_level, 'detector', name, set_pack_color=True)
        cprint('')
        cprint('   if:         ', color='grey', end='')
        cprint(i['apply_if'], color='green')
        cprint('   add groups: ', color='grey', end='')
        cprint(','.join(groups), color='magenta')


def do_detect_run():
    try:
        (code, r) = get_opsbro_local('/agent/detectors/run')
    except get_request_errors() as exp:
        logger.error(exp)
        return
    
    try:
        d = json.loads(r)
    except ValueError as exp:  # bad json
        logger.error('Bad return from the server %s' % exp)
        return
    
    print_info_title('Detectors results')
    all_groups = []
    new_groups = []
    for (k, v) in d.items():
        all_groups.extend(v['groups'])
        new_groups.extend(v['new_groups'])
    e = [('Groups', ','.join(all_groups))]
    e.append(('New groups', {'value': ','.join(new_groups), 'color': 'green'}))
    print_2tab(e)


def do_detect_state():
    try:
        (code, r) = get_opsbro_local('/agent/detectors/state')
    except get_request_errors() as exp:
        logger.error(exp)
        return
    
    try:
        groups = json.loads(r)
    except ValueError as exp:  # bad json
        logger.error('Bad return from the server %s' % exp)
        return
    
    print_info_title('Current detected groups')
    groups.sort()
    for group in groups:
        cprint(' * ', end='')
        cprint('%s' % group, color='magenta')


def do_detect_history():
    uri = '/agent/detectors/history'
    try:
        (code, r) = get_opsbro_local(uri)
    except get_request_errors() as exp:
        logger.error(exp)
        return
    
    try:
        histories = json.loads(r)
    except ValueError as exp:  # bad json
        logger.error('Bad return from the server %s' % exp)
        return
    print_h1('Detected groups history for this node')
    
    for history in histories:
        epoch = history['date']
        # We want only group type events
        entries = [entry for entry in history['entries'] if entry['type'] in ('group-add', 'group-remove')]
        if not entries:
            continue
        print_h2('  Date: %s ' % time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime(epoch)))
        for entry in entries:
            _type = entry['type']
            op = {'group-add': '+', 'group-remove': '-'}.get(_type, '?')
            color = {'group-add': 'green', 'group-remove': 'red'}.get(_type, 'grey')
            cprint(' %s %s' % (op, entry['group']), color=color)


def do_detect_wait_group(group_name, timeout=30):
    import itertools
    spinners = itertools.cycle(CHARACTERS.spinners)
    
    for i in range(timeout):
        uri = '/agent/detectors/state'
        try:
            detected_groups = get_opsbro_json(uri)
        except get_request_errors() as exp:
            logger.error(exp)
            return
            
        if group_name in detected_groups:
            cprint('\n %s ' % CHARACTERS.arrow_left, color='grey', end='')
            cprint('%s ' % CHARACTERS.check, color='green', end='')
            cprint('The group ', end='')
            cprint('%s' % group_name, color='magenta', end='')
            cprint(' is ', end='')
            cprint('detected', color='green')
            sys.exit(0)
        # Not detected? increase loop
        cprint('\r %s ' % next(spinners), color='blue', end='')  # next=> python3
        cprint('%s' % group_name, color='magenta', end='')
        cprint(' is ', end='')
        cprint('NOT DETECTED', color='magenta', end='')
        cprint(' (%d/%d)' % (i, timeout), end='')
        # As we did not \n, we must flush stdout to print it
        sys.stdout.flush()
        time.sleep(1)
    cprint("\nThe group %s was not detected after %s seconds" % (group_name, timeout))
    sys.exit(2)


exports = {
    do_detect_list      : {
        'keywords'             : ['detectors', 'list'],
        'args'                 : [
        ],
        'allow_temporary_agent': {'enabled': True, },
        'description'          : 'Show detectors list'
    },
    
    do_detect_run       : {
        'keywords'             : ['detectors', 'run'],
        'args'                 : [
        ],
        'allow_temporary_agent': {'enabled': True, },
        'description'          : 'Run detectors'
    },
    
    do_detect_state     : {
        'keywords'             : ['detectors', 'state'],
        'args'                 : [
        ],
        'allow_temporary_agent': {'enabled': True, },
        'description'          : 'Show current detected groups'
    },
    
    do_detect_history   : {
        'keywords'             : ['detectors', 'history'],
        'args'                 : [
        ],
        'allow_temporary_agent': {'enabled': True, },
        'description'          : 'Show the history of the detected groups'
    },
    
    do_detect_wait_group: {
        'keywords'             : ['detectors', 'wait-group'],
        'args'                 : [
            {'name': 'group-name', 'description': 'Name of the group to wait for being detected'},
            {'name': '--timeout', 'type': 'int', 'default': 30, 'description': 'Timeout to let the initialization'},
        ],
        'allow_temporary_agent': {'enabled': True, },
        'description'          : 'Wait until the group is detected'
    },
}
