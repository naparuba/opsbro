#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com


import json
import time

from opsbro.characters import CHARACTERS
from opsbro.log import cprint, logger
from opsbro.unixclient import get_request_errors
from opsbro.cli import get_opsbro_local, AnyAgent
from opsbro.cli_display import print_h1, print_h2

STATE_COLORS = {'COMPLIANT': 'green', 'FIXED': 'cyan', 'ERROR': 'red', 'UNKNOWN': 'grey'}
LOG_COLORS = {'SUCCESS': 'green', 'ERROR': 'red', 'FIX': 'cyan', 'COMPLIANT': 'green'}


def __print_rule_entry(rule):
    display_name = rule['name']
    mode = rule['mode']
    cprint(' > compliance > ', color='grey', end='')
    cprint('[%s] ' % (display_name.ljust(30)), color='magenta', end='')
    cprint('[mode:%10s] ' % mode, color='magenta', end='')
    
    # State:
    # * ERROR
    # * FIXED
    # * COMPLIANT
    state = rule['state']
    old_state = rule['old_state']
    state_color = STATE_COLORS.get(state, 'cyan')
    old_state_color = STATE_COLORS.get(old_state, 'cyan')
    cprint('%-10s' % old_state, color=old_state_color, end='')
    cprint(' %s ' % CHARACTERS.arrow_left, color='grey', end='')
    cprint('%-10s' % state, color=state_color)
    
    infos = rule['infos']
    # Infos can be:
    # * SUCCESS
    # * ERROR
    # * FIX
    # * COMPLIANT
    for info in infos:
        info_state = info['state']
        info_txt = info['text']
        info_color = LOG_COLORS.get(info_state, 'cyan')
        cprint('      | %-10s : %s' % (info_state, info_txt), color=info_color)


def do_compliance_state():
    # We need an agent for this
    with AnyAgent():
        uri = '/compliance/state'
        try:
            (code, r) = get_opsbro_local(uri)
        except get_request_errors(), exp:
            logger.error(exp)
            return
        
        try:
            compliances = json.loads(r)
        except ValueError, exp:  # bad json
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
                rule = pack_entries[cname]
                __print_rule_entry(rule)


def do_compliance_history():
    # We need an agent for this
    with AnyAgent():
        uri = '/compliance/history'
        try:
            (code, r) = get_opsbro_local(uri)
        except get_request_errors(), exp:
            logger.error(exp)
            return
        
        try:
            histories = json.loads(r)
        except ValueError, exp:  # bad json
            logger.error('Bad return from the server %s' % exp)
            return
        print_h1('Compliance history')
        
        for history in histories:
            epoch = history['date']
            entries = history['entries']
            print_h2('  Date: %s ' % time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime(epoch)))
            for entry in entries:
                cprint('  - %s' % entry['pack_name'], color='blue', end='')
                __print_rule_entry(entry)
            print "\n"


exports = {
    do_compliance_state  : {
        'keywords'   : ['compliance', 'state'],
        'description': 'Print the current state of the node compliance',
        'args'       : [],
    },
    
    do_compliance_history: {
        'keywords'   : ['compliance', 'history'],
        'description': 'Print the history of the compliance rules',
        'args'       : [],
    },
}
