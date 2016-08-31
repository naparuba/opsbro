#!/usr/bin/env python

# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com



import sys
import base64
import uuid
import time
import json
import socket

try:
    import requests as rq
except ImportError:
    rq = None

# try pygments for pretty printing if available
try:
    import pygments
    import pygments.lexers
    import pygments.formatters
except ImportError:
    pygments = None

from kunai.log import cprint, logger
from kunai.version import VERSION
from kunai.launcher import Launcher
from kunai.unixclient import get_json, get_local, request_errors
from kunai.cli import get_kunai_json, get_kunai_local, print_info_title, print_2tab, CONFIG, put_kunai_json
from kunai.defaultpaths import DEFAULT_LOCK_PATH

# If not requests we should exit because the
# daemon cannot be in a good shape at all
if rq is None:
    logger.error('Missing python-requests lib, please install it')
    sys.exit(2)

NO_ZONE_DEFAULT = '(no zone)'

############# ********************        MEMBERS management          ****************###########

def do_members():
    try:
        members = get_kunai_json('/agent/members').values()
    except request_errors, exp:
        logger.error('Cannot join kunai agent: %s' % exp)
        sys.exit(1)
    members = sorted(members, key=lambda e: e['name'])
    max_name_size = max([len(m['name']) for m in members])
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
        cprint('Zone: [', end='')
        cprint(z_display, color='magenta', end='')
        cprint(']')
        for m in members:
            zone = m.get('zone', NO_ZONE_DEFAULT)
            if zone != z:
                continue
            name = m['name']
            tags = m['tags']
            port = m['port']
            addr = m['addr']
            state = m['state']
            cprint('\t%s  ' % name.ljust(max_name_size), end='')
            c = {'alive': 'green', 'dead': 'red', 'suspect': 'yellow', 'leave': 'cyan'}.get(state, 'cyan')
            cprint(state.ljust(7), color=c, end='')  # 7 for the maximum state string
            s = ' %s:%s ' % (addr, port)
            s = s.ljust(max_addr_size + 2)  # +2 for the spaces
            cprint(s, end='')
            cprint(' %s ' % ','.join(tags))


def do_leave(name=''):
    # Lookup at the localhost name first
    if not name:
        try:
            (code, r) = get_kunai_local('/agent/name')
        except request_errors, exp:
            logger.error(exp)
            return
        name = r
    try:
        (code, r) = get_kunai_local('/agent/leave/%s' % name)
    except request_errors, exp:
        logger.error(exp)
        return
    
    if code != 200:
        logger.error('Node %s is missing' % name)
        print r
        return
    cprint('Node %s is set to leave state' % name, end='')
    cprint(': OK', color='green')


def do_state(name=''):
    uri = '/agent/state/%s' % name
    if not name:
        uri = '/agent/state'
    try:
        (code, r) = get_kunai_local(uri)
    except request_errors, exp:
        logger.error(exp)
        return

    try:
        d = json.loads(r)
    except ValueError, exp:  # bad json
        logger.error('Bad return from the server %s' % exp)
        return

    print 'Services:'
    for (sname, service) in d['services'].iteritems():
        state = service['state_id']
        cprint('\t%s ' % sname.ljust(20), end='')
        c = {0: 'green', 2: 'red', 1: 'yellow', 3: 'cyan'}.get(state, 'cyan')
        state = {0: 'OK', 2: 'CRITICAL', 1: 'WARNING', 3: 'UNKNOWN'}.get(state, 'UNKNOWN')
        cprint('%s - ' % state.ljust(8), color=c, end='')
        output = service['check']['output']
        cprint(output.strip(), color='grey')

    print "Checks:"
    cnames = d['checks'].keys()
    cnames.sort()
    part = ''
    for cname in cnames:
        check = d['checks'][cname]
        state = check['state_id']
        # Show like aggregation like, so look at the first name before /
        cpart = cname.split('/', 1)[0]
        if cpart == part:
            lname = cname.replace(part, ' ' * len(part))
            cprint('\t%s ' % lname.ljust(20), end='')
        else:
            cprint('\t%s ' % cname.ljust(20), end='')
        part = cpart
        c = {0: 'green', 2: 'red', 1: 'yellow', 3: 'cyan'}.get(state, 'cyan')
        state = {0: 'OK', 2: 'CRITICAL', 1: 'WARNING', 3: 'UNKNOWN'}.get(state, 'UNKNOWN')
        cprint('%s - ' % state.ljust(8), color=c, end='')
        output = check['output']
        cprint(output.strip(), color='grey')


def do_version():
    cprint(VERSION)


def do_info(show_logs):
    try:
        d = get_kunai_json('/agent/info')
    except request_errors, exp:
        logger.error('Cannot join kunai agent: %s' % exp)
        sys.exit(1)
    
    logs = d.get('logs')
    version = d.get('version')
    pid = d.get('pid')
    name = d.get('name')
    port = d.get('port')
    addr = d.get('addr')
    zone = d.get('zone')
    zone_color = 'green'
    if not zone:
        zone = NO_ZONE_DEFAULT
        zone_color = 'red'
    zone_value = {'value': zone, 'color': zone_color}
    nb_threads = d.get('threads')['nb_threads']
    httpservers = d.get('httpservers', {'internal': None, 'external': None})
    socket_path = d.get('socket')
    _uuid = d.get('uuid')
    graphite = d.get('graphite')
    statsd = d.get('statsd')
    websocket = d.get('websocket')
    dns = d.get('dns')
    tags = ','.join(d.get('tags'))
    _docker = d.get('docker')
    collectors = d.get('collectors')

    e = [('name', name), ('uuid', _uuid), ('tags', tags), ('version', version), ('pid', pid), ('port', port), ('addr', addr),
        ('zone', zone_value), ('socket', socket_path), ('threads', nb_threads)]

    # Normal agent information
    print_info_title('Kunai Daemon')
    print_2tab(e)
    
    # Normal agent information
    int_server = httpservers['external']
    if int_server:
        e = (('threads', int_server['nb_threads']), ('idle_threads', int_server['idle_threads']),
             ('queue', int_server['queue']))
        print_info_title('HTTP (LAN)')
        print_2tab(e)

    # Unix socket http daemon
    int_server = httpservers['internal']
    if int_server:
        e = (('threads', int_server['nb_threads']), ('idle_threads', int_server['idle_threads']),
             ('queue', int_server['queue']))
        print_info_title('HTTP (Unix Socket)')
        print_2tab(e)

    # Now DNS part
    print_info_title('DNS')
    if dns is None:
        cprint('No dns configured')
    else:
        w = dns
        e = [('enabled', w['enabled']), ('port', w['port']), ('domain', w['domain'])]
        print_2tab(e)
    
    # Now websocket part
    print_info_title('Websocket')
    if websocket is None:
        cprint('No websocket configured')
    else:
        w = websocket
        st = d.get('websocket_info', None)
        e = [('enabled', w['enabled']), ('port', w['port'])]
        if st:
            e.append(('Nb connexions', st.get('nb_connexions')))
        print_2tab(e)

    # Now graphite part
    print_info_title('Graphite')
    if graphite is None:
        cprint('No graphite configured')
    else:
        g = graphite
        e = [('enabled', g['enabled']), ('port', g['port']), ('udp', g['udp']), ('tcp', g['tcp'])]
        print_2tab(e)

    # Now statsd part
    print_info_title('Statsd')
    if statsd is None:
        cprint('No statsd configured')
    else:
        s = statsd
        e = [('enabled', s['enabled']), ('port', s['port']), ('interval', s['interval'])]
        print_2tab(e)

    # Now collectors part
    print_info_title('Collectors')
    cnames = collectors.keys()
    cnames.sort()
    e = []
    for cname in cnames:
        v = collectors[cname]
        color = 'green'
        if not v['active']:
            color = 'grey'
        e.append((cname, {'value': v['active'], 'color': color}))
    print_2tab(e, capitalize=False)
    
    # Now statsd part
    print_info_title('Docker')
    _d = _docker
    if _d['connected']:
        e = [('enabled', _d['enabled']), ('connected', _d['connected']),
             ('version', _d['version']), ('api', _d['api']),
             ('containers', len(_d['containers'])),
             ('images', len(_d['images'])),
             ]
    else:
        e = [
            ('enabled', {'value': _d['enabled'], 'color': 'grey'}),
            ('connected', {'value': _d['connected'], 'color': 'grey'}),
        ]

    print_2tab(e)
    
    # Show errors logs if any
    print_info_title('Logs')
    errors = logs.get('ERROR')
    warnings = logs.get('WARNING')

    # Put warning and errors in red/yellow if need only
    e = []
    if len(errors) > 0:
        e.append(('error', {'value': len(errors), 'color': 'red'}))
    else:
        e.append(('error', len(errors)))
    if len(warnings) > 0:
        e.append(('warning', {'value': len(warnings), 'color': 'yellow'}))
    else:
        e.append(('warning', len(warnings)))

    print_2tab(e)

    if show_logs:
        if len(errors) > 0:
            print_info_title('Error logs')
            for s in errors:
                cprint(s, color='red')

        if len(warnings) > 0:
            print_info_title('Warning logs')
            for s in warnings:
                cprint(s, color='yellow')

    logger.debug('Raw information: %s' % d)


# Main daemon function. Currently in blocking mode only
def do_start(daemon, cfg_dir):
    cprint('Starting kunai daemon', color='green')
    cprint('%s' % cfg_dir)
    lock_path = CONFIG.get('lock', DEFAULT_LOCK_PATH)
    l = Launcher(lock_path=lock_path, cfg_dir=cfg_dir)
    l.do_daemon_init_and_start(is_daemon=daemon)
    # Here only the last son reach this
    l.main()


def do_stop():
    try:
        (code, r) = get_kunai_local('/stop')
    except request_errors, exp:
        logger.error(exp)
        return
    cprint(r, color='green')


def do_join(seed=''):
    if seed == '':
        logger.error('Missing target argument. For example 192.168.0.1:6768')
        return
    try:
        (code, r) = get_kunai_local('/agent/join/%s' % seed)
    except request_errors, exp:
        logger.error(exp)
        return
    try:
        b = json.loads(r)
    except ValueError, exp:  # bad json
        logger.error('Bad return from the server %s' % exp)
        return
    cprint('Joining %s : ' % seed, end='')
    if b:
        cprint('OK', color='green')
    else:
        cprint('FAILED', color='red')


def do_keygen():
    k = uuid.uuid1().hex[:16]
    cprint('UDP Encryption key: (aka encryption_key)', end='')
    cprint(base64.b64encode(k), color='green')
    print ''
    try:
        import rsa
    except ImportError:
        logger.error('Missing python-rsa module for RSA keys generation, please install it')
        return
    pubkey, privkey = rsa.newkeys(2048)
    
    print "Private RSA key (2048). (aka master_key_priv for for file mfkey.priv)"
    s_privkey = privkey.save_pkcs1()
    cprint(s_privkey, color='green')
    print ''
    print "Public RSA key (2048). (aka master_key_pub for file mfkey.pub)"
    s_pubkey = pubkey.save_pkcs1()
    cprint(s_pubkey, color='green')
    print ''


def do_exec(tag='*', cmd='uname -a'):
    if cmd == '':
        logger.error('Missing command')
        return
    try:
        (code, r) = get_kunai_local('/exec/%s?cmd=%s' % (tag, cmd))
    except request_errors, exp:
        logger.error(exp)
        return
    print r
    cid = r
    print "Command group launch as cid", cid
    time.sleep(5)  # TODO: manage a real way to get the result..
    try:
        (code, r) = get_kunai_local('/exec-get/%s' % cid)
    except request_errors, exp:
        logger.error(exp)
        return
    j = json.loads(r)

    res = j['res']
    for (uuid, e) in res.iteritems():
        node = e['node']
        nname = node['name']
        color = {'alive': 'green', 'dead': 'red', 'suspect': 'yellow', 'leave': 'cyan'}.get(node['state'], 'cyan')
        cprint(nname, color=color)
        cprint('Return code:', end='')
        color = {0: 'green', 1: 'yellow', 2: 'red'}.get(e['rc'], 'cyan')
        cprint(e['rc'], color=color)
        cprint('Output:', end='')
        cprint(e['output'].strip(), color=color)
        if e['err']:
            cprint('Error:', end='')
            cprint(e['err'].strip(), color='red')
        print ''


def do_zone_change(name=''):
    if not name:
        print "Need a zone name"
        return
    print "Switching to zone", name
    try:
        r = put_kunai_json('/agent/zone', name)
    except request_errors, exp:
        logger.error(exp)
        return
    print_info_title('Result')
    print r

def do_detect_nodes():
    # Send UDP broadcast packets

    MYPORT = 6768


    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('', 0))
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    data = repr(time.time()) + '\n'
    s.sendto(data, ('255.255.255.255', MYPORT))


exports = {
    do_members: {
        'keywords'   : ['members'],
        'args'       : [],
        'description': 'List the cluster members'
    },

    do_start  : {
        'keywords'   : ['agent', 'start'],
        'args'       : [
            {'name': '--daemon', 'type': 'bool', 'default': False, 'description': 'Start kunai into the background'},
            {'name': '--cfg-dir', 'default': '/etc/kunai', 'description': 'Set a specifc configuration file'},
        ],
        'description': 'Start the kunai daemon'
    },

    do_stop   : {
        'keywords'   : ['agent', 'stop'],
        'args'       : [],
        'description': 'Stop the kunai daemon'
    },

    do_version: {
        'keywords'   : ['version'],
        'args'       : [],
        'description': 'Print the daemon version'
    },

    do_info   : {
        'keywords'   : ['info'],
        'args'       : [
            {'name': '--show-logs', 'default': False, 'description': 'Dump last warning & error logs', 'type': 'bool'},
        ],
        'description': 'Show info af a daemon'
    },

    do_keygen : {
        'keywords'   : ['keygen'],
        'args'       : [],
        'description': 'Generate a encryption key'
    },

    do_exec   : {
        'keywords'   : ['exec'],
        'args'       : [
            {'name': 'tag', 'default': '', 'description': 'Name of the node tag to execute command on'},
            {'name': 'cmd', 'default': 'uname -a', 'description': 'Command to run on the nodes'},
        ],
        'description': 'Execute a command (default to uname -a) on a group of node of the good tag (default to all)'
    },

    do_join   : {
        'keywords'   : ['join'],
        'description': 'Join another node cluster',
        'args'       : [
            {'name': 'seed', 'default': '', 'description': 'Other node to join. For example 192.168.0.1:6768'},
        ],
    },

    do_leave  : {
        'keywords'   : ['leave'],
        'description': 'Put in leave a cluster node',
        'args'       : [
            {'name'       : 'name', 'default': '',
             'description': 'Name of the node to force leave. If void, leave our local node'},
        ],
    },

    do_state  : {
        'keywords'   : ['state'],
        'description': 'Print the state of a node',
        'args'       : [
            {'name'       : 'name', 'default': '',
             'description': 'Name of the node to print state. If void, take our localhost one'},
        ],
    },
    
    do_zone_change: {
        'keywords'   : ['zone', 'change'],
        'args'       : [
            {'name': 'name', 'default': '', 'description': 'Change to the zone'},
        ],
        'description': 'Change the zone of the node'
    },
    
    do_detect_nodes: {
        'keywords'   : ['agent', 'detect'],
        'args'       : [],
        'description': 'Try to detect (broadcast) others nodes in the network'
    },
    
}
