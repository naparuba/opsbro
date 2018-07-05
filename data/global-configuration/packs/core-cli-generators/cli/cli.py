#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

from __future__ import print_function
import json
import time
import sys

from opsbro.characters import CHARACTERS
from opsbro.log import cprint, logger
from opsbro.unixclient import get_request_errors
from opsbro.cli import get_opsbro_local
from opsbro.cli_display import print_h1, print_h2
from opsbro.generator import GENERATOR_STATE_COLORS, GENERATOR_STATES


def __print_generator_entry(generator, show_diff):
    display_name = generator['name']
    cprint(' > generator > ', color='grey', end='')
    cprint('[%s] ' % (display_name.ljust(20)), color='magenta', end='')
    cprint('[%s] ' % (generator['path'].ljust(15)), color='magenta', end='')
    
    # State:
    state = generator['state']
    old_state = generator['old_state']
    state_color = GENERATOR_STATE_COLORS.get(state, 'cyan')
    old_state_color = GENERATOR_STATE_COLORS.get(old_state, 'cyan')
    cprint('%-12s' % old_state, color=old_state_color, end='')
    cprint(' %s ' % CHARACTERS.arrow_left, color='grey', end='')
    cprint('%-12s' % state, color=state_color)
    
    log = generator['log']
    if log:
        cprint('      | %s' % log, color=state_color)
    
    diff = generator['diff']
    if show_diff:
        cprint('\n'.join(diff), color='grey')


def do_generators_state(show_diff=False):
    uri = '/generators/state'
    try:
        (code, r) = get_opsbro_local(uri)
    except get_request_errors() as exp:
        logger.error(exp)
        return
    
    try:
        generators = json.loads(r)
    except ValueError as exp:  # bad json
        logger.error('Bad return from the server %s' % exp)
        return
    print_h1('Generators')
    packs = {}
    for (cname, generator) in generators.items():
        pack_name = generator['pack_name']
        if pack_name not in packs:
            packs[pack_name] = {}
        packs[pack_name][cname] = generator
    pnames = packs.keys()
    pnames.sort()
    for pname in pnames:
        pack_entries = packs[pname]
        cprint('* Pack %s' % pname, color='blue')
        cnames = pack_entries.keys()
        cnames.sort()
        for cname in cnames:
            cprint('  - %s' % pname, color='blue', end='')
            generator = pack_entries[cname]
            __print_generator_entry(generator, show_diff=show_diff)
    
    if not show_diff:
        cprint('')
        cprint('  | Note: you can see the modification diff with the --show-diff parameter', color='grey')


def do_generators_history():
    uri = '/generators/history'
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
    print_h1('Generators history')
    
    for history in histories:
        epoch = history['date']
        entries = history['entries']
        print_h2('  Date: %s ' % time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime(epoch)))
        for entry in entries:
            cprint('  - %s' % entry['pack_name'], color='blue', end='')
            __print_generator_entry(entry, show_diff=True)
        cprint("\n")


def do_generators_wait_compliant(generator_name, timeout=30):
    import itertools
    spinners = itertools.cycle(CHARACTERS.spinners)
    
    current_state = 'UNKNOWN'
    for i in range(timeout):
        uri = '/generators/state'
        try:
            (code, r) = get_opsbro_local(uri)
        except get_request_errors() as exp:
            logger.error(exp)
            return
        
        try:
            generators = json.loads(r)
        except ValueError as exp:  # bad json
            logger.error('Bad return from the server %s' % exp)
            return
        generator = None
        for (cname, c) in generators.items():
            if c['name'] == generator_name:
                generator = c
        if not generator:
            logger.error("Cannot find the generator '%s'" % generator_name)
            sys.exit(2)
        current_state = generator['state']
        cprint('\r %s ' % next(spinners), color='blue', end='')
        cprint('%s' % generator_name, color='magenta', end='')
        cprint(' is ', end='')
        cprint('%15s ' % current_state, color=GENERATOR_STATE_COLORS.get(current_state, 'cyan'), end='')
        cprint(' (%d/%d)' % (i, timeout), end='')
        # As we did not \n, we must flush stdout to print it
        sys.stdout.flush()
        if current_state == 'COMPLIANT':
            cprint("\nThe generator %s is compliant" % generator_name)
            sys.exit(0)
        logger.debug("Current state %s" % current_state)
        
        time.sleep(1)
    cprint("\nThe generator %s is not compliant after %s seconds (currently %s)" % (generator_name, timeout, current_state))
    sys.exit(2)


exports = {
    do_generators_state         : {
        'keywords'             : ['generators', 'state'],
        'description'          : 'Print the current state of the node generators',
        'args'                 : [
            {'name': '--show-diff', 'type': 'bool', 'default': False, 'description': 'If enabled, files modifications iwll be displayed'},
        ],
        'allow_temporary_agent': {'enabled': True, },
    },
    
    do_generators_history       : {
        'keywords'             : ['generators', 'history'],
        'description'          : 'Print the history of the generators',
        'args'                 : [],
        'allow_temporary_agent': {'enabled': True, },
    },
    
    do_generators_wait_compliant: {
        'keywords'             : ['generators', 'wait-compliant'],
        'args'                 : [
            {'name': 'generator-name', 'description': 'Name of the compliance rule to wait for compliance state'},
            {'name': '--timeout', 'type': 'int', 'default': 30, 'description': 'Timeout to let the initialization'},
        ],
        'allow_temporary_agent': {'enabled': True, },
        'description'          : 'Wait until the generator is in COMPLIANT state'
    },
}
