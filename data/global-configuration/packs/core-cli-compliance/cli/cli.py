#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com


import json
import time
import sys

from opsbro.characters import CHARACTERS
from opsbro.log import cprint, logger
from opsbro.unixclient import get_request_errors
from opsbro.cli import get_opsbro_local, AnyAgent
from opsbro.cli_display import print_h1, print_h2
from opsbro.compliancemgr import COMPLIANCE_LOG_COLORS, COMPLIANCE_STATE_COLORS


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


def do_compliance_state():
    # We need an agent for this
    with AnyAgent():
        uri = '/compliance/state'
        try:
            (code, r) = get_opsbro_local(uri)
        except get_request_errors() as exp:
            logger.error(exp)
            return
        
        try:
            compliances = json.loads(r)
        except ValueError as exp:  # bad json
            logger.error('Bad return from the server %s' % exp)
            return
        print_h1('Compliances')
        packs = {}
        for (cname, compliance) in compliances.iteritems():
            pack_name = compliance['pack_name']
            if pack_name not in packs:
                packs[pack_name] = {}
            packs[pack_name][cname] = compliance
        pnames = packs.keys()
        pnames.sort()
        for pname in pnames:
            pack_entries = packs[pname]
            cprint('* Pack %s' % pname, color='blue')
            cnames = pack_entries.keys()
            cnames.sort()
            for cname in cnames:
                cprint('  - %s' % pname, color='blue', end='')
                compliance = pack_entries[cname]
                __print_compliance_entry(compliance)


def do_compliance_history():
    # We need an agent for this
    with AnyAgent():
        uri = '/compliance/history'
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
            for (compliance_name, d) in entries_by_compliances.iteritems():
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
            print "\n"


def do_compliance_wait_compliant(compliance_name, timeout=30):
    import itertools
    spinners = itertools.cycle(CHARACTERS.spinners)
    
    # We need an agent for this
    with AnyAgent():
        current_state = 'UNKNOWN'
        for i in xrange(timeout):
            uri = '/compliance/state'
            try:
                (code, r) = get_opsbro_local(uri)
            except get_request_errors() as exp:
                logger.error(exp)
                return
            
            try:
                compliances = json.loads(r)
            except ValueError as exp:  # bad json
                logger.error('Bad return from the server %s' % exp)
                return
            compliance = None
            for (cname, c) in compliances.iteritems():
                if c['name'] == compliance_name:
                    compliance = c
            if not compliance:
                logger.error("Cannot find the compliance '%s'" % compliance_name)
                sys.exit(2)
            current_state = compliance['state']
            cprint('\r %s ' % spinners.next(), color='blue', end='')
            cprint('%s' % compliance_name, color='magenta', end='')
            cprint(' is ', end='')
            cprint('%15s ' % current_state, color=COMPLIANCE_STATE_COLORS.get(current_state, 'cyan'), end='')
            cprint(' (%d/%d)' % (i, timeout), end='')
            # As we did not \n, we must flush stdout to print it
            sys.stdout.flush()
            if current_state == 'COMPLIANT':
                cprint("\nThe compliance rule %s is compliant" % compliance_name)
                sys.exit(0)
            logger.debug("Current state %s" % current_state)
            
            time.sleep(1)
        cprint("\nThe compliance rule %s is not compliant after %s seconds (currently %s)" % (compliance_name, timeout, current_state))
        sys.exit(2)


exports = {
    do_compliance_state         : {
        'keywords'   : ['compliance', 'state'],
        'description': 'Print the current state of the node compliance',
        'args'       : [],
    },
    
    do_compliance_history       : {
        'keywords'   : ['compliance', 'history'],
        'description': 'Print the history of the compliance rules',
        'args'       : [],
    },
    
    do_compliance_wait_compliant: {
        'keywords'   : ['compliance', 'wait-compliant'],
        'args'       : [
            {'name': 'compliance-name', 'description': 'Name of the compliance rule to wait for compliance state'},
            {'name': '--timeout', 'type': 'int', 'default': 30, 'description': 'Timeout to let the initialization'},
        ],
        'description': 'Wait until the compliance rule is in COMPLIANT state'
    },
}
