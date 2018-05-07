#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

from __future__ import print_function
import sys
import json
import time
import itertools

from opsbro.characters import CHARACTERS
from opsbro.log import cprint, logger, sprintf
from opsbro.library import libstore
from opsbro.unixclient import get_request_errors, get_not_critical_request_errors
from opsbro.cli import get_opsbro_json, get_opsbro_local, print_info_title, put_opsbro_json, wait_for_agent_started, post_opsbro_json
from opsbro.cli_display import print_h1, print_h2
from opsbro.threadmgr import threader

NO_ZONE_DEFAULT = '(no zone)'

NODE_STATE_COLORS = {'alive': 'green', 'dead': 'red', 'suspect': 'yellow', 'leave': 'cyan'}
NODE_STATE_PREFIXS = {'alive': CHARACTERS.check, 'dead': CHARACTERS.cross, 'suspect': CHARACTERS.double_exclamation, 'leave': CHARACTERS.arrow_bottom}


############# ********************        MEMBERS management          ****************###########

def __sorted_members(m1, m2):
    n1 = m1.get('display_name', '')
    if not n1:
        n1 = m1.get('name')
    n2 = m2.get('display_name', '')
    if not n2:
        n2 = m2.get('name')
    return cmp(n1, n2)


def do_members(detail=False):
    # The information is available only if the agent is started
    wait_for_agent_started(visual_wait=True)
    
    try:
        members = get_opsbro_json('/agent/members').values()
    except get_request_errors() as exp:
        logger.error('Cannot join opsbro agent to list members: %s' % exp)
        sys.exit(1)
    members = sorted(members, cmp=__sorted_members)
    pprint = libstore.get_pprint()
    logger.debug('Raw members: %s' % (pprint.pformat(members)))
    # If there is a display_name, use it
    max_name_size = max([max(len(m['name']), len(m.get('display_name', '')) + 4) for m in members])
    max_addr_size = max([len(m['addr']) + len(str(m['port'])) + 1 for m in members])
    zones = set()
    for m in members:
        mzone = m.get('zone', '')
        if mzone == '':
            mzone = NO_ZONE_DEFAULT
        m['zone'] = mzone  # be sure to fix broken zones
        zones.add(mzone)
    zones = list(zones)
    zones.sort()
    for z in zones:
        z_display = z
        if not z:
            z_display = NO_ZONE_DEFAULT
        z_display = z_display.ljust(15)
        title_s = '%s: %s' % (sprintf('Zone', color='yellow', end=''), sprintf(z_display, color='blue', end=''))
        print_h1(title_s, raw_title=True)
        for m in members:
            zone = m.get('zone', NO_ZONE_DEFAULT)
            if zone != z:
                continue
            name = m['name']
            if m.get('display_name', ''):
                name = '[ ' + m.get('display_name') + ' ]'
            groups = m.get('groups', [])
            groups.sort()
            port = m['port']
            addr = m['addr']
            state = m['state']
            is_proxy = m.get('is_proxy', False)
            if not detail:
                cprint('  - %s > ' % zone, color='blue', end='')
                cprint('%s  ' % name.ljust(max_name_size), color='magenta', end='')
            else:
                cprint(' %s  %s  ' % (m['uuid'], name.ljust(max_name_size)), end='')
            c = NODE_STATE_COLORS.get(state, 'cyan')
            state_prefix = NODE_STATE_PREFIXS.get(state, CHARACTERS.double_exclamation)
            cprint(('%s %s' % (state_prefix, state)).ljust(9), color=c, end='')  # 7 for the maximum state string + 2 for prefix
            s = ' %s:%s ' % (addr, port)
            s = s.ljust(max_addr_size + 2)  # +2 for the spaces
            cprint(s, end='')
            if is_proxy:
                cprint('proxy ', end='')
            else:
                cprint('      ', end='')
            if detail:
                cprint('%5d' % m['incarnation'], end='')
            cprint(' %s ' % ','.join(groups))


def do_members_history():
    # The information is available only if the agent is started
    wait_for_agent_started(visual_wait=True)
    
    try:
        history_entries = get_opsbro_json('/agent/members/history')
    except get_request_errors() as exp:
        logger.error('Cannot join opsbro agent to show member history: %s' % exp)
        sys.exit(1)
    
    print_h1('History')
    for history_entry in history_entries:
        epoch_date = history_entry['date']
        # We want only group type events
        entries = [entry for entry in history_entry['entries'] if entry['type'] == 'node-state-change']
        if not entries:
            continue
        print_h2('  Date: %s ' % time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime(epoch_date)))
        for entry in entries:
            name = entry['name']
            if entry.get('display_name', ''):
                name = '[ ' + entry.get('display_name') + ' ]'
            old_state = entry['old_state']
            new_state = entry['state']
            
            old_color = NODE_STATE_COLORS.get(old_state, 'cyan')
            old_state_prefix = NODE_STATE_PREFIXS.get(old_state, CHARACTERS.double_exclamation)
            
            new_color = NODE_STATE_COLORS.get(new_state, 'cyan')
            new_state_prefix = NODE_STATE_PREFIXS.get(new_state, CHARACTERS.double_exclamation)
            
            cprint('%s  ' % name.ljust(20), color='magenta', end='')
            cprint(('%s %s' % (old_state_prefix, old_state)).ljust(9), color=old_color, end='')  # 7 for the maximum state string + 2 for prefix
            
            cprint(' %s ' % CHARACTERS.arrow_left, color='grey', end='')
            
            cprint(('%s %s' % (new_state_prefix, new_state)).ljust(9), color=new_color)  # 7 for the maximum state string + 2 for prefix


def do_leave(nuuid=''):
    # The information is available only if the agent is started
    wait_for_agent_started(visual_wait=True)
    
    # Lookup at the localhost name first
    if not nuuid:
        try:
            (code, r) = get_opsbro_local('/agent/uuid')
        except get_request_errors() as exp:
            logger.error(exp)
            return
        nuuid = r
    try:
        (code, r) = get_opsbro_local('/agent/leave/%s' % nuuid)
    except get_request_errors() as exp:
        logger.error(exp)
        return
    
    if code != 200:
        logger.error('Node %s is missing' % nuuid)
        print(r)
        return
    cprint('Node %s is set to leave state' % nuuid, end='')
    cprint(': OK', color='green')


def do_join(seed=''):
    if seed == '':
        logger.error('Missing target argument. For example 192.168.0.1:6768')
        return
    # The information is available only if the agent is started
    wait_for_agent_started(visual_wait=True)
    
    try:
        (code, r) = get_opsbro_local('/agent/join/%s' % seed)
    except get_request_errors() as exp:
        logger.error(exp)
        return
    try:
        b = json.loads(r)
    except ValueError as exp:  # bad json
        logger.error('Bad return from the server %s' % exp)
        return
    cprint('Joining %s : ' % seed, end='')
    if b:
        cprint('OK', color='green')
    else:
        cprint('FAILED', color='red')


def do_zone_change(name=''):
    if not name:
        cprint("Need a zone name")
        return
    
    cprint("Switching to zone", name)
    try:
        r = put_opsbro_json('/agent/zone', name)
    except get_request_errors() as exp:
        logger.error(exp)
        return
    print_info_title('Result')
    print(r)


def do_zone_list():
    print_h1('Known zones')
    try:
        zones = get_opsbro_json('/agent/zones')
    except get_request_errors() as exp:
        logger.error(exp)
        return
    for (zname, zone) in zones.iteritems():
        cprint(' * ', end='')
        cprint(zname, color='magenta')
        sub_zones = zone.get('sub-zones', [])
        if not sub_zones:
            continue
        cprint('  Sub zones:')
        for sub_zname in sub_zones:
            cprint('    - ', end='')
            cprint(sub_zname, color='cyan')


def __print_detection_spinner(timeout):
    spinners = itertools.cycle(CHARACTERS.spinners)
    start = time.time()
    for c in spinners:
        will_quit = False
        elapsed = time.time() - start
        # exit after 4.8 s (we did have 5s max)
        if elapsed > timeout - 0.2:  # 4.8:
            will_quit = True
            elapsed = timeout
        cprint('\r %s ' % c, color='blue', end='')
        cprint('UDP detection in progress. %.1fs/%ds.' % (elapsed, timeout), end='')
        # As we do not print the line, be sure to display it by flushing to display
        sys.stdout.flush()
        if will_quit:
            break
        time.sleep(0.25)
    # Be sure to have a void line before the other thread print
    cprint("")


def do_detect_nodes(auto_join, timeout=5):
    # The information is available only if the agent is started
    wait_for_agent_started(visual_wait=True)
    
    print_h1('UDP broadcast LAN detection')
    print("Trying to detect other nodes on the network thanks to a UDP broadcast. Will last %ds." % timeout)
    cprint(' * The detection scan will be ', end='')
    cprint('%ds' % timeout, color='magenta', end='')
    cprint(' long.')
    threader.create_and_launch(__print_detection_spinner, (timeout,), 'spinner', essential=False)
    
    # Send UDP broadcast packets from the daemon
    try:
        network_nodes = get_opsbro_json('/agent/detect?timeout=%d' % timeout, timeout=timeout + 10)
    except get_request_errors() as exp:
        logger.error('Cannot join opsbro agent to detect network nodes: %s' % exp)
        sys.exit(1)
    cprint(" * Detection is DONE")
    print_h1('Detection result')
    if len(network_nodes) == 0:
        cprint(' ERROR: ', color='red', end='')
        cprint("cannot detect (broadcast UDP) other nodes")
        sys.exit(1)
    cprint("Other network nodes detected on this network:")
    cprint('  Name                                 Zone        Address:port          Proxy    Groups')
    for node in network_nodes:
        cprint('  %-35s  %-10s  %s:%d  %5s     %s' % (node['name'], node['zone'], node['addr'], node['port'], node['is_proxy'], ','.join(node['groups'])))
    if not auto_join:
        cprint('NOTICE: ', color='blue', end='')
        cprint("Auto join (--auto-join) is not enabled, so don't try to join theses nodes")
        return
    # try to join theses nodes so :)
    all_proxys = [node for node in network_nodes if node['is_proxy']]
    not_proxys = [node for node in network_nodes if not node['is_proxy']]
    if all_proxys:
        node = all_proxys.pop()
        cprint("A proxy node is detected, using it: %s (%s:%d)" % (node['name'], node['addr'], node['port']))
        to_connect = '%s:%d' % (node['addr'], node['port'])
    else:
        node = not_proxys.pop()
        cprint("No proxy node detected. Using a standard one: %s (%s:%d)" % (node['name'], node['addr'], node['port']))
        to_connect = '%s:%d' % (node['addr'], node['port'])
    do_join(to_connect)


def do_wait_event(event_type, timeout=30):
    # The information is available only if the agent is started
    wait_for_agent_started(visual_wait=True)
    
    import itertools
    spinners = itertools.cycle(CHARACTERS.spinners)
    
    for i in xrange(timeout):
        uri = '/agent/event/%s' % event_type
        logger.info('ASK FOR EVENT %s' % event_type)
        try:
            evt = get_opsbro_json(uri, timeout=1)  # slow timeout to allow fast looping
        # Timemouts: just loop
        except get_not_critical_request_errors() as exp:
            logger.debug('Asking for event: get timeout (%s), skiping this turn' % exp)
            evt = None
        except get_request_errors() as exp:
            logger.error('Cannot ask for event %s because there is a critical error: %s' % (event_type, exp))
            sys.exit(2)
        
        if evt is not None:
            cprint('\n %s ' % CHARACTERS.arrow_left, color='grey', end='')
            cprint('%s ' % CHARACTERS.check, color='green', end='')
            cprint('The event ', end='')
            cprint('%s' % event_type, color='magenta', end='')
            cprint(' is ', end='')
            cprint('detected', color='green')
            sys.exit(0)
        # Not detected? increase loop
        cprint('\r %s ' % spinners.next(), color='blue', end='')
        cprint('%s' % event_type, color='magenta', end='')
        cprint(' is ', end='')
        cprint('NOT DETECTED', color='magenta', end='')
        cprint(' (%d/%d)' % (i, timeout), end='')
        # As we did not \n, we must flush stdout to print it
        sys.stdout.flush()
        time.sleep(1)
    cprint("\nThe event %s was not detected after %s seconds" % (event_type, timeout))
    sys.exit(2)


def do_gossip_add_event(event_type):
    # The information is available only if the agent is started
    wait_for_agent_started(visual_wait=True)
    
    try:
        r = post_opsbro_json('/agent/event', {'event_type': event_type})
    except get_request_errors() as exp:
        logger.error(exp)
        sys.exit(2)
    cprint('\n %s ' % CHARACTERS.arrow_left, color='grey', end='')
    cprint('%s ' % CHARACTERS.check, color='green', end='')
    cprint('The event ', end='')
    cprint('%s' % event_type, color='magenta', end='')
    cprint(' is ', end='')
    cprint('added', color='green')


def do_wait_members(name='', display_name='', group='', count=1, timeout=30):
    # The information is available only if the agent is started
    wait_for_agent_started(visual_wait=True)
    
    import itertools
    spinners = itertools.cycle(CHARACTERS.spinners)
    
    for i in xrange(timeout):
        try:
            members = get_opsbro_json('/agent/members').values()
        except get_request_errors() as exp:
            logger.error(exp)
            sys.exit(2)
        if name:
            for m in members:
                if m['name'] == name:
                    cprint('\n %s ' % CHARACTERS.arrow_left, color='grey', end='')
                    cprint('%s ' % CHARACTERS.check, color='green', end='')
                    cprint('The member ', end='')
                    cprint('%s' % name, color='magenta', end='')
                    cprint(' is ', end='')
                    cprint('detected', color='green')
                    sys.exit(0)
        elif display_name:
            for m in members:
                if m['display_name'] == display_name:
                    cprint('\n %s ' % CHARACTERS.arrow_left, color='grey', end='')
                    cprint('%s ' % CHARACTERS.check, color='green', end='')
                    cprint('The member ', end='')
                    cprint('%s' % display_name, color='magenta', end='')
                    cprint(' is ', end='')
                    cprint('detected', color='green')
                    sys.exit(0)
        
        elif group:
            founded = []
            for m in members:
                if group in m['groups']:
                    founded.append(m)
            
            if len(founded) > count:
                cprint('\n %s ' % CHARACTERS.arrow_left, color='grey', end='')
                cprint('%s ' % CHARACTERS.check, color='green', end='')
                cprint('The group ', end='')
                cprint('%s' % group, color='magenta', end='')
                cprint(' is ', end='')
                cprint('detected', color='green')
                cprint(' with %d members' % len(founded), end='')
                sys.exit(0)
        
        # Not detected? increase loop
        cprint('\r %s ' % spinners.next(), color='blue', end='')
        if name:
            cprint('%s' % name, color='magenta', end='')
        elif display_name:
            cprint('%s' % display_name, color='magenta', end='')
        else:
            cprint('%s' % group, color='magenta', end='')
        cprint(' is ', end='')
        cprint('NOT DETECTED', color='magenta', end='')
        cprint(' (%d/%d)' % (i, timeout), end='')
        # As we did not \n, we must flush stdout to print it
        sys.stdout.flush()
        time.sleep(1)
    cprint("\nThe name/display_name/group was not detected after %s seconds" % (timeout))
    sys.exit(2)


exports = {
    do_members         : {
        'keywords'   : ['gossip', 'members'],
        'args'       : [
            {'name': '--detail', 'type': 'bool', 'default': False, 'description': 'Show detail mode for the cluster members'},
        ],
        'description': 'List the cluster members'
    },
    
    do_members_history : {
        'keywords'   : ['gossip', 'history'],
        'args'       : [
        ],
        'description': 'Show the history of the gossip nodes'
    },
    
    do_join            : {
        'keywords'   : ['gossip', 'join'],
        'description': 'Join another node cluster',
        'args'       : [
            {'name': 'seed', 'default': '', 'description': 'Other node to join. For example 192.168.0.1:6768'},
        ],
    },
    
    do_leave           : {
        'keywords'   : ['gossip', 'leave'],
        'description': 'Put in leave a cluster node',
        'args'       : [
            {'name'       : 'name', 'default': '',
             'description': 'UUID of the node to force leave. If void, leave our local node'},
        ],
    },
    
    do_zone_change     : {
        'keywords'             : ['gossip', 'zone', 'change'],
        'args'                 : [
            {'name': 'name', 'default': '', 'description': 'Change to the zone'},
        ],
        'allow_temporary_agent': {'enabled': True, },
        'description'          : 'Change the zone of the node'
    },
    
    do_zone_list       : {
        'keywords'             : ['gossip', 'zone', 'list'],
        'args'                 : [
        ],
        'allow_temporary_agent': {'enabled': True, },
        'description'          : 'List all known zones of the node'
    },
    
    do_detect_nodes    : {
        'keywords'   : ['gossip', 'detect'],
        'args'       : [
            {'name': '--auto-join', 'default': False, 'description': 'Try to join the first detected proxy node. If no proxy is founded, join the first one.', 'type': 'bool'},
            {'name': '--timeout', 'type': 'int', 'default': 5, 'description': 'Timeout used for the discovery'},
        ],
        'description': 'Try to detect (broadcast) others nodes in the network'
    },
    
    do_wait_event      : {
        'keywords'   : ['gossip', 'events', 'wait'],
        'args'       : [
            {'name': 'event-type', 'description': 'Name of the event to wait for'},
            {'name': '--timeout', 'type': 'int', 'default': 30, 'description': 'Timeout to let the initialization'},
        ],
        'description': 'Wait until the event is detected'
    },
    
    do_gossip_add_event: {
        'keywords'   : ['gossip', 'events', 'add'],
        'args'       : [
            {'name': 'event-type', 'description': 'Name of the event to add'},
        ],
        'description': 'Add a event to the gossip members'
    },
    
    do_wait_members    : {
        'keywords'   : ['gossip', 'wait-members'],
        'args'       : [
            {'name': '--name', 'description': 'Name of the members to wait for be alive'},
            {'name': '--display-name', 'description': 'Display name of the members to wait for be alive'},
            {'name': '--group', 'description': 'Group of the members to wait for be alive'},
            {'name': '--count', 'description': 'Number of alive member of the group to wait for'},
            {'name': '--timeout', 'type': 'int', 'default': 30, 'description': 'Timeout to let the initialization'},
        ],
        'description': 'Wait until alive members are detected based on name, display name or group'
    },
    
}
