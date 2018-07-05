#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

from __future__ import print_function
import time
import sys

from opsbro.characters import CHARACTERS
from opsbro.log import cprint, logger
from opsbro.unixclient import get_request_errors
from opsbro.cli import get_opsbro_local, put_opsbro_json
from opsbro.cli_display import print_h1, print_h2, get_terminal_size
from opsbro.compliancemgr import COMPLIANCE_LOG_COLORS, COMPLIANCE_STATES, COMPLIANCE_STATE_COLORS
from opsbro.jsonmgr import jsoner


def __print_rule_entry(rule):
    cprint('    - ', end='', color='grey')
    rule_name = rule['name']
    cprint('[%s] ' % (rule_name.ljust(30)), color='magenta', end='')
    
    # State:
    state = rule['state']
    old_state = rule['old_state']
    state_color = COMPLIANCE_STATE_COLORS.get(state, 'cyan')
    old_state_color = COMPLIANCE_STATE_COLORS.get(old_state, 'cyan')
    cprint('%-12s' % old_state, color=old_state_color, end='')
    cprint(' %s ' % CHARACTERS.arrow_left, color='grey', end='')
    cprint('%-12s' % state, color=state_color)
    
    infos = rule['infos']
    # Infos can be:
    # * SUCCESS
    # * ERROR
    # * FIX
    # * COMPLIANT
    for info in infos:
        info_state = info['state']
        info_txt = info['text']
        info_color = COMPLIANCE_LOG_COLORS.get(info_state, 'cyan')
        cprint('      | %-10s : %s' % (info_state, info_txt), color=info_color)


def __print_compliance_entry(compliance):
    display_name = compliance['name']
    mode = compliance['mode']
    cprint(' > compliance > ', color='grey', end='')
    cprint('[%s] ' % (display_name.ljust(30)), color='magenta', end='')
    cprint('[mode:%10s] ' % mode, color='magenta', end='')
    
    # State:
    state = compliance['state']
    old_state = compliance['old_state']
    state_color = COMPLIANCE_STATE_COLORS.get(state, 'cyan')
    old_state_color = COMPLIANCE_STATE_COLORS.get(old_state, 'cyan')
    cprint('%-12s' % old_state, color=old_state_color, end='')
    cprint(' %s ' % CHARACTERS.arrow_left, color='grey', end='')
    cprint('%-12s' % state, color=state_color)
    
    rules = compliance['rules']
    for rule in rules:
        __print_rule_entry(rule)


def do_compliance_state(compliance_name=''):
    uri = '/compliance/state'
    try:
        (code, r) = get_opsbro_local(uri)
    except get_request_errors() as exp:
        logger.error(exp)
        return
    
    try:
        compliances = jsoner.loads(r)
    except ValueError as exp:  # bad json
        logger.error('Bad return from the server %s' % exp)
        return
    print_h1('Compliances')
    packs = {}
    for (cname, compliance) in compliances.items():
        if compliance_name and compliance['name'] != compliance_name:
            continue
        pack_name = compliance['pack_name']
        if pack_name not in packs:
            packs[pack_name] = {}
        packs[pack_name][cname] = compliance
    pnames = list(packs.keys())  # python3
    pnames.sort()
    for pname in pnames:
        pack_entries = packs[pname]
        cprint('* Pack %s' % pname, color='blue')
        cnames = list(pack_entries.keys())  # python3
        cnames.sort()
        for cname in cnames:
            cprint('  - %s' % pname, color='blue', end='')
            compliance = pack_entries[cname]
            __print_compliance_entry(compliance)


def do_compliance_history():
    uri = '/compliance/history'
    try:
        (code, r) = get_opsbro_local(uri)
    except get_request_errors() as exp:
        logger.error(exp)
        return
    
    try:
        histories = jsoner.loads(r)
    except ValueError as exp:  # bad json
        logger.error('Bad return from the server %s' % exp)
        return
    print_h1('Compliance history')
    
    for history in histories:
        epoch = history['date']
        entries = history['entries']
        print_h2('  Date: %s ' % time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime(epoch)))
        entries_by_compliances = {}
        for entry in entries:
            compliance_name = entry['compliance_name']
            pack_name = entry['pack_name']
            mode = entry['mode']
            if compliance_name not in entries_by_compliances:
                entries_by_compliances[compliance_name] = {'pack_name': pack_name, 'mode': mode, 'entries': []}
            entries_by_compliances[compliance_name]['entries'].append(entry)
        for (compliance_name, d) in entries_by_compliances.items():
            pack_name = d['pack_name']
            mode = d['mode']
            entries = d['entries']
            cprint('  - %s' % pack_name, color='blue', end='')
            cprint(' > compliance > ', color='grey', end='')
            cprint('[%s] ' % (compliance_name.ljust(30)), color='magenta', end='')
            cprint('[mode:%10s] ' % mode, color='magenta')
            for entry in entries:
                # rule_name = entry['name']
                # cprint('[%s] ' % (rule_name.ljust(30)), color='magenta', end='')
                __print_rule_entry(entry)
        cprint("\n")


def do_compliance_wait_compliant(compliance_name, timeout=30, exit_if_ok=True):
    import itertools
    spinners = itertools.cycle(CHARACTERS.spinners)
    
    current_state = COMPLIANCE_STATES.UNKNOWN
    for i in range(timeout):  # no xrange in python3
        uri = '/compliance/state'
        try:
            (code, r) = get_opsbro_local(uri)
        except get_request_errors() as exp:
            logger.error(exp)
            return
        
        try:
            compliances = jsoner.loads(r)
        except ValueError as exp:  # bad json
            logger.error('Bad return from the server %s' % exp)
            return
        compliance = None
        for (cname, c) in compliances.items():
            if c['name'] == compliance_name:
                compliance = c
        if not compliance:
            logger.error("Cannot find the compliance '%s'" % compliance_name)
            sys.exit(2)
        logger.debug('Current compliance data', compliance)
        current_step = ''
        current_state = compliance['state']
        if compliance['is_running']:
            current_state = COMPLIANCE_STATES.RUNNING
            current_step = compliance['current_step']
        # Clean line
        try:
            terminal_height, terminal_width = get_terminal_size()
        except:  # beware, maybe we don't have a tty
            terminal_width = 100
        cprint('\r' + ' ' * terminal_width, end='')
        cprint('\r %s ' % next(spinners), color='blue', end='')  # no spinnner.next in python3
        cprint('%s' % compliance_name, color='magenta', end='')
        cprint(' is ', end='')
        cprint('%15s ' % current_state, color=COMPLIANCE_STATE_COLORS.get(current_state, 'cyan'), end='')
        cprint(' (%d/%d)' % (i, timeout), end='')
        if current_step:
            cprint(' [ in step ', end='')
            cprint(current_step, color='magenta', end='')
            cprint(' ]', end='')
        # As we did not \n, we must flush stdout to print it
        sys.stdout.flush()
        if current_state == COMPLIANCE_STATES.COMPLIANT:
            cprint("\nThe compliance rule %s is compliant" % compliance_name)
            if exit_if_ok:
                sys.exit(0)
            else:
                return
        logger.debug("Current state %s" % current_state)
        
        time.sleep(1)
    cprint("\nThe compliance rule %s is not compliant after %s seconds (currently %s)" % (compliance_name, timeout, current_state))
    sys.exit(2)


def do_compliance_launch(compliance_name, timeout=30):
    cprint("Launching compliance %s" % compliance_name)
    try:
        founded = put_opsbro_json('/compliance/launch', compliance_name)
    except get_request_errors() as exp:
        logger.error(exp)
        return
    if not founded:
        cprint('ERROR: cannot find the compliance %s (founded=%s)' % (compliance_name, founded), color='red')
        sys.exit(2)
    do_compliance_wait_compliant(compliance_name, timeout=timeout, exit_if_ok=False)
    do_compliance_state(compliance_name=compliance_name)


exports = {
    do_compliance_state         : {
        'keywords'             : ['compliance', 'state'],
        'description'          : 'Print the current state of the node compliance',
        'args'                 : [
            {'name': 'compliance-name', 'description': 'If set, only show the compliance with this rule. If not, show all compliance'},
        ],
        'allow_temporary_agent': {'enabled': True, },
        
    },
    
    do_compliance_history       : {
        'keywords'             : ['compliance', 'history'],
        'description'          : 'Print the history of the compliance rules',
        'args'                 : [],
        'allow_temporary_agent': {'enabled': True, },
    },
    
    do_compliance_wait_compliant: {
        'keywords'             : ['compliance', 'wait-compliant'],
        'args'                 : [
            {'name': 'compliance-name', 'description': 'Name of the compliance rule to wait for compliance state'},
            {'name': '--timeout', 'type': 'int', 'default': 30, 'description': 'Timeout to let the initialization'},
        ],
        'allow_temporary_agent': {'enabled': True, },
        'description'          : 'Wait until the compliance rule is in COMPLIANT state'
    },
    
    do_compliance_launch        : {
        'keywords'             : ['compliance', 'launch'],
        'args'                 : [
            {'name': 'compliance-name', 'description': 'Name of the compliance rule to force to be launched and then for compliance state'},
            {'name': '--timeout', 'type': 'int', 'default': 30, 'description': 'Timeout to let the initialization'},
        ],
        'allow_temporary_agent': {'enabled': True, },
        'description'          : 'Force a rule to be launched and wait until the compliance rule is in COMPLIANT state'
    },
}
