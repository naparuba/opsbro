#!/usr/bin/env python

# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com



import json

from opsbro.characters import CHARACTERS
from opsbro.log import cprint, logger
from opsbro.unixclient import get_request_errors
from opsbro.cli import get_opsbro_local
from opsbro.cli_display import print_h1

NO_ZONE_DEFAULT = '(no zone)'


def do_state(name=''):
    uri = '/agent/state/%s' % name
    if not name:
        uri = '/agent/state'
    try:
        (code, r) = get_opsbro_local(uri)
    except get_request_errors(), exp:
        logger.error(exp)
        return
    
    try:
        d = json.loads(r)
    except ValueError, exp:  # bad json
        logger.error('Bad return from the server %s' % exp)
        return
    
    services = d['services']
    print_h1('Services')
    if len(services) == 0:
        cprint('No services', color='grey')
    else:
        for (sname, service) in services.iteritems():
            state = service['state_id']
            cprint('\t%s ' % sname.ljust(20), end='')
            c = {0: 'green', 2: 'red', 1: 'yellow', 3: 'cyan'}.get(state, 'cyan')
            state = {0: 'OK', 2: 'CRITICAL', 1: 'WARNING', 3: 'UNKNOWN'}.get(state, 'UNKNOWN')
            cprint('%s - ' % state.ljust(8), color=c, end='')
            output = service['check']['output']
            cprint(output.strip(), color='grey')
    
    checks = d['checks']
    if len(checks) == 0:
        cprint('No checks', color='grey')
        return  # nothing to do more
    
    print_h1('Checks')
    packs = {}
    for (cname, check) in checks.iteritems():
        pack_name = check['pack_name']
        if pack_name not in packs:
            packs[pack_name] = {}
        packs[pack_name][cname] = check
    pnames = packs.keys()
    pnames.sort()
    for pname in pnames:
        pack_entries = packs[pname]
        cprint('* Pack %s' % pname, color='blue')
        cnames = pack_entries.keys()
        cnames.sort()
        for cname in cnames:
            check = pack_entries[cname]
            check_display_name = check['display_name']
            
            cprint('  - %s' % pname, color='blue', end='')
            cprint(' > checks > ', color='grey', end='')
            cprint('%s ' % (check_display_name.ljust(30)), color='magenta', end='')
            
            state = check['state_id']
            c = {0: 'green', 2: 'red', 1: 'yellow', 3: 'cyan'}.get(state, 'cyan')
            state = {0: '%s OK' % CHARACTERS.check, 2: '%s CRITICAL' % CHARACTERS.cross, 1: '%s WARNING' % CHARACTERS.double_exclamation, 3: '%s UNKNOWN' % CHARACTERS.double_exclamation}.get(state, 'UNKNOWN')
            cprint('%s' % state.ljust(10), color=c)
            # Now print output the line under
            output = check['output']
            output_lines = output.strip().splitlines()
            for line in output_lines:
                cprint(' ' * 4 + '| ' + line, color='grey')


exports = {
    do_state: {
        'keywords'   : ['monitoring', 'state'],
        'description': 'Print the state of a node',
        'args'       : [
            {'name'       : 'name', 'default': '',
             'description': 'Name of the node to print state. If void, take our localhost one'},
        ],
    },
    
}
