#!/usr/bin/env python

# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com


import json

from opsbro.log import cprint, logger
from opsbro.unixclient import get_request_errors
from opsbro.cli import get_opsbro_local, print_info_title, print_2tab
from opsbro.cli_display import print_element_breadcumb


def do_detect_list():
    try:
        (code, r) = get_opsbro_local('/agent/detectors')
    except get_request_errors(), exp:
        logger.error(exp)
        return
    
    try:
        d = json.loads(r)
    except ValueError, exp:  # bad json
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
    except get_request_errors(), exp:
        logger.error(exp)
        return
    
    try:
        d = json.loads(r)
    except ValueError, exp:  # bad json
        logger.error('Bad return from the server %s' % exp)
        return
    
    print_info_title('Detectors results')
    all_groups = []
    new_groups = []
    for (k, v) in d.iteritems():
        all_groups.extend(v['groups'])
        new_groups.extend(v['new_groups'])
    e = [('Groups', ','.join(all_groups))]
    e.append(('New groups', {'value': ','.join(new_groups), 'color': 'green'}))
    print_2tab(e)


exports = {
    do_detect_list: {
        'keywords'   : ['detectors', 'list'],
        'args'       : [
        ],
        'description': 'Show detectors list'
    },
    
    do_detect_run : {
        'keywords'   : ['detectors', 'run'],
        'args'       : [
        ],
        'description': 'Run detectors'
    },
}
