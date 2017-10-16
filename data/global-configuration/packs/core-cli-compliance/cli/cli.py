#!/usr/bin/env python

# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com



import json

from opsbro.characters import CHARACTERS
from opsbro.log import cprint, logger
from opsbro.unixclient import get_request_errors
from opsbro.cli import get_opsbro_local, AnyAgent
from opsbro.cli_display import print_h1


def do_compliance_list():
    # We need an agent for this
    with AnyAgent():
        uri = '/compliance/'
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
                compliance = pack_entries[cname]
                display_name = compliance['display_name']
                
                cprint('  - %s' % pname, color='blue', end='')
                cprint(' > compliance > ', color='grey', end='')
                cprint('[%s] ' % (display_name.ljust(30)), color='magenta', end='')
                cprint(' %s ' % CHARACTERS.arrow_left, color='grey', end='')
                rule_state = compliance['rule']
                # maybe there is no valid rule
                if rule_state is None:
                    cprint('(no valid rule)', color='grey')
                    continue
                # State:
                # * ERROR
                # * FIXED
                # * COMPLIANT
                state = rule_state['state']
                state_color = {'COMPLIANT': 'green', 'FIXED': 'cyan', 'ERROR': 'red'}.get(state, 'cyan')
                cprint('%10s' % state, color=state_color)
                infos = rule_state['infos']
                # Infos can be:
                # * SUCCESS
                # * ERROR
                # * FIX
                info_colors = {'SUCCESS': 'green', 'ERROR': 'red', 'FIX': 'cyan'}
                for (info_state, info_txt) in infos:
                    info_color = info_colors.get(info_state, 'cyan')
                    cprint('  | %10s : %s' % (info_state, info_txt), color=info_color)


exports = {
    do_compliance_list: {
        'keywords'   : ['compliance', 'state'],
        'description': 'Print the state of the node compliance',
        'args'       : [],
    },
    
}
