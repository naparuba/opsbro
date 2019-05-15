#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

from __future__ import print_function
import os
import sys
import time
import itertools
import uuid
import base64

from opsbro.characters import CHARACTERS
from opsbro.log import cprint, logger
from opsbro.library import libstore
from opsbro.unixclient import get_request_errors, get_not_critical_request_errors
from opsbro.cli import get_opsbro_json, get_opsbro_local, wait_for_agent_started, post_opsbro_json
from opsbro.yamleditor import parameter_set_to_main_yml
from opsbro.cli_display import print_h1, print_h2
from opsbro.threadmgr import threader
from opsbro.jsonmgr import jsoner
from opsbro.util import my_sort, my_cmp, unicode_to_bytes
from opsbro.gossip import NODE_STATES

NO_ZONE_DEFAULT = '(no zone)'

NODE_STATE_COLORS = {NODE_STATES.ALIVE  : 'green',
                     NODE_STATES.DEAD   : 'red',
                     NODE_STATES.SUSPECT: 'yellow',
                     NODE_STATES.LEAVE  : 'cyan',
                     NODE_STATES.UNKNOWN: 'grey',
                     }

NODE_STATE_PREFIXS = {NODE_STATES.ALIVE  : CHARACTERS.check,
                      NODE_STATES.DEAD   : CHARACTERS.cross,
                      NODE_STATES.SUSPECT: CHARACTERS.double_exclamation,
                      NODE_STATES.LEAVE  : CHARACTERS.arrow_bottom,
                      NODE_STATES.UNKNOWN: CHARACTERS.arrow_bottom,
                      }


class _ZONE_TYPES:
    OTHER = 0
    OUR_ZONE = 1
    HIGHER = 2
    LOWER = 3
    TOO_HIGH = 4


_ALL_ZONE_TYPES = [_ZONE_TYPES.OTHER, _ZONE_TYPES.OUR_ZONE, _ZONE_TYPES.HIGHER, _ZONE_TYPES.LOWER, _ZONE_TYPES.TOO_HIGH]

_ZONE_TYPE_COLORS = {
    _ZONE_TYPES.OTHER   : 'grey',
    _ZONE_TYPES.OUR_ZONE: 'magenta',
    _ZONE_TYPES.HIGHER  : 'blue',
    _ZONE_TYPES.LOWER   : 'green',
    _ZONE_TYPES.TOO_HIGH: 'grey',
}

_ZONE_TYPE_LABEL = {
    _ZONE_TYPES.OTHER   : 'Other zone',
    _ZONE_TYPES.OUR_ZONE: 'Your zone',
    _ZONE_TYPES.HIGHER  : 'Higher zone',
    _ZONE_TYPES.LOWER   : 'Lower zone',
    _ZONE_TYPES.TOO_HIGH: 'Too high zone',
}

_ZONE_TYPE_DESCRIPTION = {
    _ZONE_TYPES.OTHER   : 'Zone not in your higher or lower ones',
    _ZONE_TYPES.OUR_ZONE: 'In your zone you known all nodes',
    _ZONE_TYPES.HIGHER  : 'You only know about higher zone proxy nodes',
    _ZONE_TYPES.LOWER   : 'You know all nodes in this lower zone',
    _ZONE_TYPES.TOO_HIGH: 'You know nothing about too high zone',
}


############# ********************        MEMBERS management          ****************###########

def __sorted_members(m1, m2):
    n1 = m1.get('display_name', '')
    if not n1:
        n1 = m1.get('name')
    n2 = m2.get('display_name', '')
    if not n2:
        n2 = m2.get('name')
    return my_cmp(n1, n2)


def _get_zone_tree():
    try:
        zones = get_opsbro_json('/agent/zones')
    except get_request_errors() as exp:
        logger.error(exp)
        return
    
    all_zones = list(zones.values())
    zones_tree = zones
    
    # We are building the zone tree, so link real object in other zone
    for zone in zones_tree.values():
        sub_zones = {}
        for sub_zone_name in zone.get('sub-zones', []):
            sub_zone = zones_tree.get(sub_zone_name, None)
            sub_zones[sub_zone_name] = sub_zone
        zone['sub-zones'] = sub_zones
        zone['members'] = []  # repare a list for the members we can add inside
        zone['distance_from_my_zone'] = 999
    
    # Set if the zone is top/lower if not our own zone
    for zone in zones_tree.values():
        zone['type'] = _ZONE_TYPES.OTHER
    
    # And finally delete the zone that are not in top level
    to_del = set()
    for (zname, zone) in zones_tree.items():
        for sub_zname in zone['sub-zones']:
            to_del.add(sub_zname)
    for zname in to_del:
        del zones_tree[zname]
    
    for zone in zones_tree.values():
        _flag_top_lower_zone(zone)
    
    return zones_tree, all_zones


def _get_zone_from_tree(zones, search_zone_name):
    for zone_name, zone in zones.items():
        if zone_name == search_zone_name:
            return zone
        zone = _get_zone_from_tree(zone['sub-zones'], search_zone_name)
        if zone is not None:
            return zone
    return None


def _do_print_zone_members(zone, show_detail, max_name_size=15, max_addr_size=15, level=0):
    zone_name = zone['name']
    z_display = zone_name
    if not zone_name:
        z_display = NO_ZONE_DEFAULT
    z_display = z_display.ljust(15)
    cprint('  | ' * level, color='grey', end='')
    cprint(' - ', color='grey', end='')
    
    zone_type = zone['type']
    label = _ZONE_TYPE_LABEL[zone_type]
    color = _ZONE_TYPE_COLORS[zone_type]
    cprint(z_display, color=color, end='')
    cprint(' (%s) ' % label, color=color)
    
    # title_s = '%s: %s' % (sprintf('Zone', color='yellow', end=''), sprintf(z_display, color='blue', end=''))
    # print_h1(title_s, raw_title=True)
    members = zone['members']
    for m in members:
        name = m['name']
        if m.get('display_name', ''):
            name = '[ ' + m.get('display_name') + ' ]'
        groups = m.get('groups', [])
        groups.sort()
        port = m['port']
        addr = m['addr']
        state = m['state']
        is_proxy = m.get('is_proxy', False)
        cprint('  | ' * level, color='grey', end='')
        if not show_detail:
            cprint('  %s ' % CHARACTERS.corner_bottom_left, end='')
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
        if show_detail:
            cprint('%5d' % m['incarnation'], end='')
        cprint(' %s ' % ','.join(groups))
    
    for sub_zone in zone['sub-zones'].values():
        _do_print_zone_members(sub_zone, show_detail=show_detail, max_name_size=max_name_size, max_addr_size=max_addr_size, level=level + 1)


def do_members(detail=False):
    pprint = libstore.get_pprint()
    # The information is available only if the agent is started
    wait_for_agent_started(visual_wait=True)
    
    zones_tree, all_zones = _get_zone_tree()
    
    # print("ZONE TREE: %s" % zones_tree)
    
    try:
        all_members = get_opsbro_json('/agent/members').values()
    except get_request_errors() as exp:
        logger.error('Cannot join opsbro agent to list members: %s' % exp)
        sys.exit(1)
    
    for member in all_members:
        member_zone = member['zone']
        zone = _get_zone_from_tree(zones_tree, member_zone)
        # print("IN ZONE: %s" % zone)
        zone['members'].append(member)
    
    # zones = set()
    # for m in members:
    #     mzone = m.get('zone', '')
    #     if mzone == '':
    #         mzone = NO_ZONE_DEFAULT
    #     m['zone'] = mzone  # be sure to fix broken zones
    #     zones.add(mzone)
    
    # print('ALL ZONES: %s' % all_zones)
    for zone in all_zones:
        zone['members'] = my_sort(zone['members'], cmp_f=__sorted_members)
        
        logger.debug('Raw members: %s' % (pprint.pformat(zone['members'])))
    
    # If there is a display_name, use it
    max_name_size = max([max(len(m['name']), len(m.get('display_name', '')) + 4) for m in all_members])
    max_addr_size = max([len(m['public_addr']) + len(str(m['port'])) + 1 for m in all_members])
    
    for zone in zones_tree.values():
        _do_print_zone_members(zone, show_detail=detail, max_name_size=max_name_size, max_addr_size=max_addr_size, level=0)


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
            nuuid = get_opsbro_json('/agent/uuid')
        except get_request_errors() as exp:
            logger.error('Cannot join opsbro agent to get our uuid: %s' % exp)
            sys.exit(2)
    uri = '/agent/leave/%s' % nuuid
    try:
        (code, r) = get_opsbro_local(uri)
    except get_request_errors() as exp:
        logger.error(exp)
        return
    
    if code != 200:
        logger.error('Node %s is missing (return=%s)' % (nuuid, r))
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
        b = jsoner.loads(r)
    except ValueError as exp:  # bad json
        logger.error('Bad return from the server %s' % exp)
        return
    cprint('Joining %s : ' % seed, end='')
    if b:
        cprint('OK', color='green')
    else:
        cprint('FAILED', color='red')


def do_ping(node):
    # The information is available only if the agent is started
    wait_for_agent_started(visual_wait=True)
    
    try:
        node_obj = get_opsbro_json('/agent/query/guess/%s' % node)
    except get_request_errors() as exp:
        logger.error('Cannot query the node: %s' % exp)
        sys.exit(2)
    if node_obj is None:
        cprint('FAILED: cannot find the node %s' % node, color='red')
        sys.exit(2)
    node_uuid = node_obj['uuid']
    
    try:
        ping_result = get_opsbro_json('/agent/ping/%s' % node_uuid)
    except get_request_errors() as exp:
        logger.error('Cannot launch the node ping: %s' % exp)
        sys.exit(2)
    if 'error' in ping_result:
        cprint('FAILED: %s' % ping_result['error'], color='red')
        sys.exit(2)
    node_state = ping_result['state']
    display_name = node_obj['display_name']
    if not display_name:
        display_name = node_obj['name']
    
    state_color = NODE_STATE_COLORS.get(node_state)
    state_char = NODE_STATE_PREFIXS.get(node_state)
    cprint(' %s ' % state_char, color=state_color, end='')
    cprint('%-15s ' % display_name, color='magenta', end='')
    cprint('is: ', end='')
    cprint(node_state, color=state_color)
    
    # If not alive, it's an error
    if node_state != NODE_STATES.ALIVE:
        sys.exit(2)


def do_zone_change(name=''):
    if not name:
        cprint("Need a zone name")
        return
    
    # Directly change into the main file, and it the daemon is up, change it too
    parameter_set_to_main_yml('node-zone', name)


def _flag_top_lower_zone(zone, from_our_zone=False, distance_from_my_zone=999):
    r = _ZONE_TYPES.OTHER
    if zone['is_our_zone']:
        zone['type'] = _ZONE_TYPES.OUR_ZONE
        from_our_zone = True
        r = _ZONE_TYPES.HIGHER
        distance_from_my_zone = 0
        zone['distance_from_my_zone'] = distance_from_my_zone
    else:  # not our zone, so can be from it (we are lower)
        if from_our_zone:
            zone['type'] = _ZONE_TYPES.LOWER
            distance_from_my_zone += 1
            zone['distance_from_my_zone'] = distance_from_my_zone
    
    for sub_zone in zone['sub-zones'].values():
        from_sub_zone, distance_from_my_zone = _flag_top_lower_zone(sub_zone, from_our_zone, distance_from_my_zone=distance_from_my_zone)
        if from_sub_zone == _ZONE_TYPES.HIGHER:  # the sub zone say we are a higher level one
            r = _ZONE_TYPES.HIGHER
            distance_from_my_zone -= 1
            zone['distance_from_my_zone'] = distance_from_my_zone
            if abs(zone['distance_from_my_zone']) >= 2:
                zone['type'] = _ZONE_TYPES.TOO_HIGH
            else:
                zone['type'] = _ZONE_TYPES.HIGHER
    
    return r, zone['distance_from_my_zone']


# Do print the zone but at the level X
def _print_zone(zname, zone, level):
    cprint('  | ' * level, color='grey', end='')
    cprint(' * ', end='')
    cprint(zname, color='magenta', end='')
    
    if zone['have_gossip_key']:
        cprint(' [ This zone have a gossip key ] ', color='blue', end='')
    
    zone_type = zone['type']
    cprint(' ( %s ) ' % _ZONE_TYPE_LABEL[zone_type], color=_ZONE_TYPE_COLORS[zone_type])
    
    sub_zones = zone.get('sub-zones', {})
    if not sub_zones:
        return
    cprint('  | ' * level, color='grey', end='')
    cprint('  Sub zones:')
    sub_znames = sub_zones.keys()
    sub_znames.sort()
    for sub_zname in sub_znames:
        sub_zone = sub_zones[sub_zname]
        _print_zone(sub_zname, sub_zone, level + 1)


def do_zone_list():
    print_h1('Known zones')
    zones_tree, all_zones = _get_zone_tree()
    
    # Now print it
    zone_names = zones_tree.keys()
    zone_names.sort()
    
    for zname in zone_names:
        zone = zones_tree[zname]
        _print_zone(zname, zone, 0)
    
    cprint('')
    print_h1('Zones types legend')
    for zone_type in _ALL_ZONE_TYPES:
        label = _ZONE_TYPE_LABEL[zone_type]
        color = _ZONE_TYPE_COLORS[zone_type]
        description = _ZONE_TYPE_DESCRIPTION[zone_type]
        cprint(' - ', end='')
        cprint('%-15s' % label, color=color, end='')
        cprint(' : %s' % description)


def _save_key(key_string, zone_name, key_path):
    with open(key_path, 'wb') as f:
        f.write(unicode_to_bytes(key_string))
    
    cprint('%s OK the key is saved as file %s' % (CHARACTERS.check, key_path))
    
    # Try to send the information to the agent, so it can reload the key
    try:
        get_opsbro_json('/agent/zones-keys/reload/%s' % zone_name)
    except get_request_errors():
        cprint('  | The agent seems to not be started. Skipping hot key reload.', color='grey')
        return


def do_zone_key_generate(zone, erase=False):
    from opsbro.defaultpaths import DEFAULT_CFG_DIR
    from opsbro.configurationmanager import ZONE_KEYS_DIRECTORY_NAME
    from opsbro.encrypter import GOSSIP_KEY_FILE_FORMAT
    print_h1('Generate a new key for the zone %s' % zone)
    
    key_path = os.path.join(DEFAULT_CFG_DIR, ZONE_KEYS_DIRECTORY_NAME, GOSSIP_KEY_FILE_FORMAT % zone)
    
    if os.path.exists(key_path) and not erase:
        cprint('ERROR: the key %s is already existing', color='red')
        cprint('  %s Note: You can use the --erase parameter to erase over an existing key' % (CHARACTERS.corner_bottom_left), color='grey')
        sys.exit(2)
    
    k = uuid.uuid1().hex[:16]
    b64_k = base64.b64encode(k)
    cprint('Encryption key for the zone ', end='')
    cprint(zone, color='magenta', end='')
    cprint(' :', end='')
    cprint(b64_k, color='green')
    _save_key(b64_k, zone, key_path)


def do_zone_key_import(zone, key, erase=False):
    from opsbro.defaultpaths import DEFAULT_CFG_DIR
    from opsbro.configurationmanager import ZONE_KEYS_DIRECTORY_NAME
    from opsbro.encrypter import GOSSIP_KEY_FILE_FORMAT
    
    key_path = os.path.join(DEFAULT_CFG_DIR, ZONE_KEYS_DIRECTORY_NAME, GOSSIP_KEY_FILE_FORMAT % zone)
    
    if os.path.exists(key_path) and not erase:
        cprint('ERROR: the key %s is already existing', color='red')
        cprint('  %s Note: You can use the --erase parameter to erase over an existing key' % (CHARACTERS.corner_bottom_left), color='grey')
        sys.exit(2)
    # check key is base64(len16)
    try:
        raw_key = base64.b64decode(key)
    except TypeError:  # bad key
        cprint('ERROR: the key is not valid. (not base4 encoded)', color='red')
        sys.exit(2)
    if len(raw_key) != 16:
        cprint('ERROR: the key is not valid. (not 128bits)', color='red')
        sys.exit(2)
    
    # Note: key is the original b64 encoded one, we did check it
    _save_key(key, zone, key_path)


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
        cprint('  %-35s  %-10s  %s:%d  %5s     %s' % (node['name'], node['zone'], node['public_addr'], node['port'], node['is_proxy'], ','.join(node['groups'])))
    if not auto_join:
        cprint('NOTICE: ', color='blue', end='')
        cprint("Auto join (--auto-join) is not enabled, so don't try to join theses nodes")
        return
    
    # try to join theses nodes so :)
    # NOTE: sort by uuid so we are always joining the same nodes
    # and so we don't have split network if possible (common node)
    all_proxys = sorted([node for node in network_nodes if node['is_proxy']], key=lambda n: n['uuid'])
    not_proxys = sorted([node for node in network_nodes if not node['is_proxy']], key=lambda n: n['uuid'])
    if all_proxys:
        node = all_proxys.pop()
        cprint("A proxy node is detected, using it: %s (%s:%d)" % (node['name'], node['public_addr'], node['port']))
        to_connect = '%s:%d' % (node['public_addr'], node['port'])
    else:
        node = not_proxys.pop()
        cprint("No proxy node detected. Using a standard one: %s (%s:%d)" % (node['name'], node['public_addr'], node['port']))
        to_connect = '%s:%d' % (node['public_addr'], node['port'])
    do_join(to_connect)


def do_wait_event(event_type, timeout=30):
    # The information is available only if the agent is started
    wait_for_agent_started(visual_wait=True)
    
    import itertools
    spinners = itertools.cycle(CHARACTERS.spinners)
    
    for i in range(timeout):
        uri = '/agent/event/%s' % event_type
        logger.debug('ASK FOR EVENT %s' % event_type)
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
        cprint('\r %s ' % next(spinners), color='blue', end='')
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


def do_wait_members(name=None, display_name=None, group=None, count=1, timeout=30):
    # The information is available only if the agent is started
    wait_for_agent_started(visual_wait=True)
    
    import itertools
    spinners = itertools.cycle(CHARACTERS.spinners)
    
    for i in range(timeout):
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
        cprint('\r %s ' % next(spinners), color='blue', end='')
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
    do_members          : {
        'keywords'   : ['gossip', 'members'],
        'args'       : [
            {'name': '--detail', 'type': 'bool', 'default': False, 'description': 'Show detail mode for the cluster members'},
        ],
        'description': 'List the cluster members'
    },
    
    do_members_history  : {
        'keywords'   : ['gossip', 'history'],
        'args'       : [
        ],
        'description': 'Show the history of the gossip nodes'
    },
    
    do_join             : {
        'keywords'   : ['gossip', 'join'],
        'description': 'Join another node cluster',
        'args'       : [
            {'name': 'seed', 'default': '', 'description': 'Other node to join. For example 192.168.0.1:6768'},
        ],
    },
    
    do_ping             : {
        'keywords'   : ['gossip', 'ping'],
        'description': 'Ping another node of the cluster',
        'args'       : [
            {'name': 'node', 'default': '', 'description': 'uuid, name or display name of the node to ping'},
        ],
    },
    
    do_leave            : {
        'keywords'   : ['gossip', 'leave'],
        'description': 'Put in leave a cluster node',
        'args'       : [
            {'name'       : 'name', 'default': '',
             'description': 'UUID of the node to force leave. If void, leave our local node'},
        ],
    },
    
    do_zone_change      : {
        'keywords'   : ['gossip', 'zone', 'change'],
        'args'       : [
            {'name': 'name', 'default': '', 'description': 'Change to the zone '},
        ],
        'description': 'Change the zone of the node in the configuration and in the running agent if started'
    },
    
    do_zone_list        : {
        'keywords'             : ['gossip', 'zone', 'list'],
        'args'                 : [
        ],
        'allow_temporary_agent': {'enabled': True, },
        'description'          : 'List all known zones of the node'
    },
    
    do_zone_key_generate: {
        'keywords'   : ['gossip', 'zone', 'key', 'generate'],
        'args'       : [
            {'name': '--zone', 'description': 'Name of zone to generate a key for'},
            {'name': '--erase', 'type': 'bool', 'default': False, 'description': 'Erase the key if already exiting.'},
        ],
        'description': 'Generate a gossip encryption key for the zone'
    },
    
    do_zone_key_import  : {
        'keywords'   : ['gossip', 'zone', 'key', 'import'],
        'args'       : [
            {'name': '--zone', 'description': 'Name of zone to import the key for'},
            {'name': '--key', 'description': 'Key to import.'},
            {'name': '--erase', 'type': 'bool', 'default': False, 'description': 'Erase the key if already exiting.'},
        ],
        'description': 'Import a gossip encryption key for the zone'
    },
    
    do_detect_nodes     : {
        'keywords'   : ['gossip', 'detect'],
        'args'       : [
            {'name': '--auto-join', 'default': False, 'description': 'Try to join the first detected proxy node. If no proxy is founded, join the first one.', 'type': 'bool'},
            {'name': '--timeout', 'type': 'int', 'default': 5, 'description': 'Timeout used for the discovery'},
        ],
        'description': 'Try to detect (broadcast) others nodes in the network'
    },
    
    do_wait_event       : {
        'keywords'   : ['gossip', 'events', 'wait'],
        'args'       : [
            {'name': 'event-type', 'description': 'Name of the event to wait for'},
            {'name': '--timeout', 'type': 'int', 'default': 30, 'description': 'Timeout to let the initialization'},
        ],
        'description': 'Wait until the event is detected'
    },
    
    do_gossip_add_event : {
        'keywords'   : ['gossip', 'events', 'add'],
        'args'       : [
            {'name': 'event-type', 'description': 'Name of the event to add'},
        ],
        'description': 'Add a event to the gossip members'
    },
    
    do_wait_members     : {
        'keywords'   : ['gossip', 'wait-members'],
        'args'       : [
            {'name': '--name', 'default': None, 'description': 'Name of the members to wait for be alive'},
            {'name': '--display-name', 'default': None, 'description': 'Display name of the members to wait for be alive'},
            {'name': '--group', 'default': None, 'description': 'Group of the members to wait for be alive'},
            {'name': '--count', 'type': 'int', 'default': 1, 'description': 'Number of alive member of the group to wait for'},
            {'name': '--timeout', 'type': 'int', 'default': 30, 'description': 'Timeout to let the initialization'},
        ],
        'description': 'Wait until alive members are detected based on name, display name or group'
    },
    
}
