#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

from __future__ import print_function
import sys
import time

from opsbro.characters import CHARACTERS
from opsbro.log import cprint, logger
from opsbro.unixclient import get_request_errors, get_not_critical_request_errors
from opsbro.cli import get_opsbro_json, wait_for_agent_started
from opsbro.raft import RAFT_STATE_COLORS, RAFT_MINIMAL_MEMBERS_NB


def do_raft_state():
    # The information is available only if the agent is started
    wait_for_agent_started(visual_wait=True)
    
    try:
        raft_infos = get_opsbro_json('/raft/state')
    except get_request_errors() as exp:
        logger.error('Cannot join opsbro agent to get RAFT state: %s' % exp)
        sys.exit(1)
    
    raft_state = raft_infos['state']
    raft_state_color = RAFT_STATE_COLORS.get(raft_state)
    nb_nodes = raft_infos['nb_nodes']
    leader = raft_infos['leader']
    
    # If there are too few nodes, then the RAFT is not allowed (too few to avoid split brain)
    if nb_nodes < RAFT_MINIMAL_MEMBERS_NB:
        cprint('WARNING %s ' % CHARACTERS.double_exclamation, color='yellow', end='')
        cprint('The RAFT algorithm need at least ', end='')
        cprint('%d ' % RAFT_MINIMAL_MEMBERS_NB, color='magenta', end='')
        cprint('nodes, but currently only ', end='')
        cprint('%d ' % nb_nodes, color='magenta', end='')
        cprint('are available in your zone.')
        sys.exit(1)
    
    cprint('Current node RAFT state: ', end='')
    cprint(raft_state, color=raft_state_color)
    if leader:
        name = leader['display_name']
        if not name:
            name = leader['name']
        addr = leader['addr']
        cprint('Current RAFT leader: ', end='')
        cprint(name, color='magenta', end='')
        cprint(' ( ', end='')
        cprint(addr, color='magenta', end='')
        cprint(' )')
    else:
        cprint('WARNING %s ' % CHARACTERS.double_exclamation, color='yellow', end='')
        cprint('Currently there is no leader on the RAFT cluster')
        sys.exit(1)


def do_raft_wait_leader(timeout=30):
    import itertools
    spinners = itertools.cycle(CHARACTERS.spinners)
    
    for i in range(timeout):
        try:
            raft_infos = get_opsbro_json('/raft/state', timeout=1)
        except get_not_critical_request_errors():  # we did fail to call it in 1s (timeout), but we allow a global timeout, skip this
            continue
        except get_request_errors() as exp:
            logger.error('Cannot join opsbro agent to get RAFT state: %s' % exp)
            sys.exit(1)
        
        raft_state = raft_infos['state']
        raft_state_color = RAFT_STATE_COLORS.get(raft_state)
        leader = raft_infos['leader']
        
        if leader is not None:
            name = leader['display_name']
            if not name:
                name = leader['name']
            addr = leader['addr']
            cprint('\n %s ' % CHARACTERS.arrow_left, color='grey', end='')
            cprint('%s ' % CHARACTERS.check, color='green', end='')
            cprint('The RAFT leader is ', end='')
            cprint(name, color='magenta', end='')
            cprint(' ( ', end='')
            cprint(addr, color='magenta', end='')
            cprint(' )')
            sys.exit(0)
        # Not detected? increase loop
        cprint('\r %s ' % next(spinners), color='blue', end='')
        cprint('The RAFT leader is still not elected. Current node state: ', color='magenta', end='')
        cprint(raft_state, color=raft_state_color, end='')
        cprint(' (%d/%d)' % (i, timeout), end='')
        # As we did not \n, we must flush stdout to print it
        sys.stdout.flush()
        time.sleep(1)
    cprint("\nThe RAFT leader is still not elected after %s seconds" % timeout)
    sys.exit(2)


exports = {
    do_raft_state      : {
        'keywords'   : ['raft', 'state'],
        'args'       : [],
        'description': 'Show the state of the internal RAFT cluster of your nodes'
    },
    
    do_raft_wait_leader: {
        'keywords'             : ['raft', 'wait-leader'],
        'args'                 : [
            {'name': '--timeout', 'type': 'int', 'default': 30, 'description': 'Timeout to let for the raft algorithm to have a leader'},
        ],
        'allow_temporary_agent': {'enabled': True, },
        'description'          : 'Wait until the RAFT algorithm got a leader'
    },
}
