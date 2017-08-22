#!/usr/bin/env python

# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com



import sys
import base64
import uuid
import time
import json
import os
import pprint

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

if os.name == 'nt':
    import win32serviceutil
    import win32api
    from opsbro.windows_service.windows_service import Service

from opsbro.log import cprint, logger
from opsbro.info import VERSION
from opsbro.launcher import Launcher
from opsbro.unixclient import get_json, get_local, request_errors
from opsbro.cli import get_opsbro_json, get_opsbro_local, print_info_title, print_2tab, CONFIG, put_opsbro_json
from opsbro.defaultpaths import DEFAULT_LOCK_PATH

# If not requests we should exit because the
# daemon cannot be in a good shape at all
if rq is None:
    logger.error('Missing python-requests lib, please install it')
    sys.exit(2)

NO_ZONE_DEFAULT = '(no zone)'


############# ********************        MEMBERS management          ****************###########

def do_members(detail=False):
    try:
        members = get_opsbro_json('/agent/members').values()
    except request_errors, exp:
        logger.error('Cannot join opsbro agent: %s' % exp)
        sys.exit(1)
    members = sorted(members, key=lambda e: e['name'])
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
        cprint('Zone: [', end='')
        cprint(z_display, color='magenta', end='')
        cprint(']')
        for m in members:
            zone = m.get('zone', NO_ZONE_DEFAULT)
            if zone != z:
                continue
            name = m['name']
            if m.get('display_name', ''):
                name = '[ ' + m.get('display_name') + ' ]'
            tags = m['tags']
            port = m['port']
            addr = m['addr']
            state = m['state']
            is_proxy = m.get('is_proxy', False)
            if not detail:
                cprint('\t%s  ' % name.ljust(max_name_size), end='')
            else:
                cprint(' %s  %s  ' % (m['uuid'], name.ljust(max_name_size)), end='')
            c = {'alive': 'green', 'dead': 'red', 'suspect': 'yellow', 'leave': 'cyan'}.get(state, 'cyan')
            cprint(state.ljust(7), color=c, end='')  # 7 for the maximum state string
            s = ' %s:%s ' % (addr, port)
            s = s.ljust(max_addr_size + 2)  # +2 for the spaces
            cprint(s, end='')
            if is_proxy:
                cprint('proxy ', end='')
            else:
                cprint('      ', end='')
            if detail:
                cprint('%5d' % m['incarnation'])
            cprint(' %s ' % ','.join(tags))


def do_leave(nuuid=''):
    # Lookup at the localhost name first
    if not nuuid:
        try:
            (code, r) = get_opsbro_local('/agent/uuid')
        except request_errors, exp:
            logger.error(exp)
            return
        nuuid = r
    try:
        (code, r) = get_opsbro_local('/agent/leave/%s' % nuuid)
    except request_errors, exp:
        logger.error(exp)
        return
    
    if code != 200:
        logger.error('Node %s is missing' % nuuid)
        print r
        return
    cprint('Node %s is set to leave state' % nuuid, end='')
    cprint(': OK', color='green')


def do_state(name=''):
    uri = '/agent/state/%s' % name
    if not name:
        uri = '/agent/state'
    try:
        (code, r) = get_opsbro_local(uri)
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


def __call_service_handler():
    def __ctrlHandler(ctrlType):
        return True
    
    
    win32api.SetConsoleCtrlHandler(__ctrlHandler, True)
    win32serviceutil.HandleCommandLine(Service)


def do_service_install():
    # hack argv for the install
    sys.argv = ['c:\\opsbro\\bin\\opsbro', 'install']
    __call_service_handler()


def do_service_remove():
    # hack argv for the remove
    sys.argv = ['c:\\opsbro\\bin\\opsbro', 'remove']
    __call_service_handler()


def do_info(show_logs):
    try:
        d = get_opsbro_json('/agent/info')
    except request_errors, exp:
        logger.error('Cannot join opsbro agent: %s' % exp)
        sys.exit(1)
    logs = d.get('logs')
    version = d.get('version')
    pid = d.get('pid')
    name = d.get('name')
    display_name = d.get('display_name', '')
    # A failback to display name is the name (hostname)
    if not display_name:
        display_name = name
    else:  # show it's a display name
        display_name = '[ ' + display_name + ' ]'
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
    
    e = [('name', name), ('display name', display_name), ('uuid', _uuid), ('tags', tags), ('version', version), ('pid', pid), ('port', port), ('addr', addr),
         ('zone', zone_value), ('socket', socket_path), ('threads', nb_threads)]
    
    # Normal agent information
    print_info_title('OpsBro Daemon')
    print_2tab(e)
    
    # Normal agent information
    int_server = httpservers.get('external', None)
    if int_server:
        e = (('threads', int_server['nb_threads']), ('idle_threads', int_server['idle_threads']),
             ('queue', int_server['queue']))
        print_info_title('HTTP (LAN)')
        print_2tab(e)
    else:
        print_info_title('HTTP (LAN) info not available')
    
    # Unix socket http daemon
    int_server = httpservers.get('internal', None)
    if int_server:
        e = (('threads', int_server['nb_threads']), ('idle_threads', int_server['idle_threads']),
             ('queue', int_server['queue']))
        print_info_title('HTTP (Unix Socket)')
        print_2tab(e)
    else:
        print_info_title('HTTP (Unix Socket) info not available')
    
    # Now DNS part
    print_info_title('DNS')
    if not dns or 'dns_configuration' not in dns:
        cprint('No dns configured')
    else:
        w = dns['dns_configuration']
        e = [('enabled', w['enabled']), ('port', w['port']), ('domain', w['domain'])]
        print_2tab(e)
    
    # Now websocket part
    print_info_title('Websocket')
    if not websocket or 'websocket_configuration' not in websocket:
        cprint('No websocket configured')
    else:
        w = websocket['websocket_configuration']
        st = websocket.get('websocket_info', None)
        e = [('enabled', w['enabled']), ('port', w['port'])]
        if st:
            e.append(('Nb connexions', st.get('nb_connexions')))
        print_2tab(e)
    
    # Now graphite part
    print_info_title('Graphite')
    if not graphite or 'graphite_configuration' not in graphite:
        cprint('No graphite configured')
    else:
        g = graphite['graphite_configuration']
        e = [('enabled', g['enabled']), ('port', g['port']), ('udp', g['udp']), ('tcp', g['tcp'])]
        print_2tab(e)
    
    # Now statsd part
    print_info_title('Statsd')
    if not statsd or 'statsd_configuration' not in statsd:
        cprint('No statsd configured')
    else:
        s = statsd['statsd_configuration']
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
    cprint('Starting opsbro daemon', color='green')
    cprint('%s' % cfg_dir)
    lock_path = CONFIG.get('lock', DEFAULT_LOCK_PATH)
    l = Launcher(lock_path=lock_path, cfg_dir=cfg_dir)
    l.do_daemon_init_and_start(is_daemon=daemon)
    # Here only the last son reach this
    l.main()


def do_stop():
    try:
        (code, r) = get_opsbro_local('/stop')
    except request_errors, exp:
        logger.error(exp)
        return
    cprint(r, color='green')


def do_join(seed=''):
    if seed == '':
        logger.error('Missing target argument. For example 192.168.0.1:6768')
        return
    try:
        (code, r) = get_opsbro_local('/agent/join/%s' % seed)
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
        (code, r) = get_opsbro_local('/exec/%s?cmd=%s' % (tag, cmd))
    except request_errors, exp:
        logger.error(exp)
        return
    print r
    cid = r
    print "Command group launch as cid", cid
    time.sleep(5)  # TODO: manage a real way to get the result..
    try:
        (code, r) = get_opsbro_local('/exec-get/%s' % cid)
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
        r = put_opsbro_json('/agent/zone', name)
    except request_errors, exp:
        logger.error(exp)
        return
    print_info_title('Result')
    print r


def do_detect_nodes(auto_join):
    print "Trying to detect other nodes on the network thanks to a UDP broadcast. Will last 3s."
    # Send UDP broadcast packets from the daemon
    try:
        network_nodes = get_opsbro_json('/agent/detect')
    except request_errors, exp:
        logger.error('Cannot join opsbro agent: %s' % exp)
        sys.exit(1)
    print "Detection is DONE.\nDetection result:"
    if len(network_nodes) == 0:
        print "Cannot detect (broadcast UDP) other nodes."
        sys.exit(1)
    print "Other network nodes detected on this network:"
    print '  Name                                 Zone        Address:port          Proxy    Tags'
    for node in network_nodes:
        print '  %-35s  %-10s  %s:%d  %5s     %s' % (node['name'], node['zone'], node['addr'], node['port'], node['is_proxy'], ','.join(node['tags']))
    if not auto_join:
        print "Auto join (--auto-join) is not enabled, so don't try to join theses nodes"
        return
    # try to join theses nodes so :)
    all_proxys = [node for node in network_nodes if node['is_proxy']]
    not_proxys = [node for node in network_nodes if not node['is_proxy']]
    if all_proxys:
        node = all_proxys.pop()
        print "A proxy node is detected, using it: %s (%s:%d)" % (node['name'], node['addr'], node['port'])
        to_connect = '%s:%d' % (node['addr'], node['port'])
    else:
        node = not_proxys.pop()
        print "No proxy node detected. Using a standard one: %s (%s:%d)" % (node['name'], node['addr'], node['port'])
        to_connect = '%s:%d' % (node['addr'], node['port'])
    do_join(to_connect)


# Sort threads by user time, if same, sort by name
def _sort_threads(t1, t2):
    t1_cpu = t1['user_time']
    t2_cpu = t2['user_time']
    t1_name = t1['name']
    t2_name = t2['name']
    if t1_cpu == t2_cpu:
        return cmp(t1_name, t2_name)
    else:  # bigger first
        return -cmp(t1_cpu, t2_cpu)


def __get_cpu_time_percent_display(t, age):
    thread_user = t['user_time']
    thread_system = t['system_time']
    if thread_system == -1 or thread_user == -1:
        return ('unknown', 'unknown')
    if age == 0:
        return ('unknown', 'unknown')
    # ok we are good :)
    return ('%.2f' % (100 * thread_user / age), '%.3f' % (100 * thread_system / age))


def do_show_threads():
    try:
        data = get_opsbro_json('/threads/')
    except request_errors, exp:
        logger.error('Cannot join opsbro agent: %s' % exp)
        sys.exit(1)
    all_threads = data['threads']
    process = data['process']
    age = data['age']
    
    # Cut the threads into 2 lists: always here, and the others
    all_daemon_threads = [t for t in all_threads if t['essential']]
    all_not_daemon_threads = [t for t in all_threads if not t['essential']]
    
    # Put essential ones into part
    threads_into_parts = {}
    for t in all_daemon_threads:
        part = t['part'].capitalize()
        if not t:
            part = '(unknown)'
        if part not in threads_into_parts:
            threads_into_parts[part] = {'name': part, 'user_time': 0.0, 'system_time': 0.0, 'threads': []}
        e = threads_into_parts[part]
        e['user_time'] += t['user_time']
        e['system_time'] += t['system_time']
        e['threads'].append(t)
    
    # Sort threads inside the parts
    for (pname, e) in threads_into_parts.iteritems():
        e['threads'].sort(_sort_threads)
    
    # Now have parts sort by their times (from bigger to min)
    parts_sorts_by_cpu_usage = threads_into_parts.values()
    parts_sorts_by_cpu_usage = sorted(parts_sorts_by_cpu_usage, key=lambda e: -e['user_time'])
    
    # Then by name
    parts_sorts_by_name = threads_into_parts.values()
    parts_sorts_by_name = sorted(parts_sorts_by_name, key=lambda e: e['name'])
    
    all_daemon_threads.sort(_sort_threads)
    
    all_not_daemon_threads.sort(_sort_threads)
    upercent, syspercent = __get_cpu_time_percent_display(process, age)
    cprint('Total process CPU consumption:  ', color='blue', end='')
    cprint('cpu(user):%s%%  ' % upercent, color='magenta', end='')
    cprint('cpu(system):%s%%' % syspercent)
    print "\n"
    
    print "Summary of CPU consumption based on opsbro parts:"
    for p in parts_sorts_by_cpu_usage:
        upercent, syspercent = __get_cpu_time_percent_display(p, age)
        cprint('  * [ ', end='')
        cprint('%-15s' % p['name'], color='blue', end='')
        cprint(' ]  ', end='')
        cprint('cpu(user):%s%%  ' % upercent, color='magenta', end='')
        cprint('cpu(system):%s%%' % syspercent)
    print ""
    print "Daemon threads (persistent):"
    for p in parts_sorts_by_name:
        cprint('[ ', end='')
        cprint('%-15s' % p['name'], color='blue', end='')
        cprint(' ]  ')
        for t in p['threads']:
            upercent, syspercent = __get_cpu_time_percent_display(t, age)
            print '   * %-55s  thread id:%5d   cpu(user):%s%%   cpu(system):%s%%' % (t['name'], t['tid'], upercent, syspercent)
    if all_not_daemon_threads:
        print "\nTemporary threads:"
        for t in all_not_daemon_threads:
            upercent, syspercent = __get_cpu_time_percent_display(t, age)
            print '   Name:%-55s  id:%d   cpu(user):%s%%   cpu(system):%s%%' % (t['name'], t['tid'], upercent, syspercent)


def do_list_follow_log():
    try:
        parts = get_opsbro_json('/log/parts/')
    except request_errors, exp:
        logger.error('Cannot join opsbro agent: %s' % exp)
        sys.exit(1)
    parts.sort()
    print "Available parts to follow logs:"
    for p in parts:
        print "  * %s" % p


def do_follow_log(part=''):
    if not part:
        return
    try:
        import fcntl
    except ImportError:
        print "Error: this action is not availabe on your OS."
        return
    
    print 'Try to follow log part %s' % part
    p = '/tmp/opsbro-follow-%s' % part
    
    # Clean fifo to be sure to clean previous runs
    if os.path.exists(p):
        os.unlink(p)
    
    if not os.path.exists(p):
        os.mkfifo(p)
    
    colors = {'DEBUG': 'magenta', 'INFO': 'blue', 'WARNING': 'yellow', 'ERROR': 'red'}
    try:
        w = 0.001
        while True:
            with open(p, 'rb', 0) as fifo:
                fd = fifo.fileno()
                flag = fcntl.fcntl(fd, fcntl.F_GETFD)
                fcntl.fcntl(fd, fcntl.F_SETFL, flag | os.O_NONBLOCK)
                while True:
                    try:
                        data = fifo.read()
                    except IOError:
                        w *= 2
                        w = min(w, 0.1)
                        time.sleep(w)
                        continue
                    if len(data) == 0:
                        break
                    w = 0.001
                    for line in data.splitlines():
                        already_print = False
                        for (k, color) in colors.iteritems():
                            if k in line:
                                cprint(line, color=color)
                                already_print = True
                                break
                        if not already_print:
                            print line
    finally:
        try:
            print "\nDisabling log dumping for the part %s" % part
            os.unlink(p)
        except:
            pass


exports = {
    do_members        : {
        'keywords'   : ['members'],
        'args'       : [
            {'name': '--detail', 'type': 'bool', 'default': False, 'description': 'Show detail mode for the cluster members'},
        ],
        'description': 'List the cluster members'
    },
    
    do_start          : {
        'keywords'   : ['agent', 'start'],
        'args'       : [
            {'name': '--daemon', 'type': 'bool', 'default': False, 'description': 'Start opsbro into the background'},
            {'name': '--cfg-dir', 'default': '/etc/opsbro', 'description': 'Set a specifc configuration file'},
        ],
        'description': 'Start the opsbro daemon'
    },
    
    do_stop           : {
        'keywords'   : ['agent', 'stop'],
        'args'       : [],
        'description': 'Stop the opsbro daemon'
    },
    
    do_service_install: {
        'keywords'   : ['agent', 'service-install'],
        'args'       : [],
        'description': 'Install windows service'
    },
    
    do_service_remove : {
        'keywords'   : ['agent', 'service-remove'],
        'args'       : [],
        'description': 'Remove windows service'
    },
    
    do_version        : {
        'keywords'   : ['version'],
        'args'       : [],
        'description': 'Print the daemon version'
    },
    
    do_info           : {
        'keywords'   : ['info'],
        'args'       : [
            {'name': '--show-logs', 'default': False, 'description': 'Dump last warning & error logs', 'type': 'bool'},
        ],
        'description': 'Show info af a daemon'
    },
    
    do_keygen         : {
        'keywords'   : ['keygen'],
        'args'       : [],
        'description': 'Generate a encryption key'
    },
    
    do_exec           : {
        'keywords'   : ['exec'],
        'args'       : [
            {'name': 'tag', 'default': '', 'description': 'Name of the node tag to execute command on'},
            {'name': 'cmd', 'default': 'uname -a', 'description': 'Command to run on the nodes'},
        ],
        'description': 'Execute a command (default to uname -a) on a group of node of the good tag (default to all)'
    },
    
    do_join           : {
        'keywords'   : ['join'],
        'description': 'Join another node cluster',
        'args'       : [
            {'name': 'seed', 'default': '', 'description': 'Other node to join. For example 192.168.0.1:6768'},
        ],
    },
    
    do_leave          : {
        'keywords'   : ['leave'],
        'description': 'Put in leave a cluster node',
        'args'       : [
            {'name'       : 'name', 'default': '',
             'description': 'UUID of the node to force leave. If void, leave our local node'},
        ],
    },
    
    do_state          : {
        'keywords'   : ['state'],
        'description': 'Print the state of a node',
        'args'       : [
            {'name'       : 'name', 'default': '',
             'description': 'Name of the node to print state. If void, take our localhost one'},
        ],
    },
    
    do_zone_change    : {
        'keywords'   : ['zone', 'change'],
        'args'       : [
            {'name': 'name', 'default': '', 'description': 'Change to the zone'},
        ],
        'description': 'Change the zone of the node'
    },
    
    do_detect_nodes   : {
        'keywords'   : ['agent', 'detect'],
        'args'       : [
             {'name': '--auto-join', 'default': False, 'description': 'Try to join the first detected proxy node. If no proxy is founded, join the first one.', 'type': 'bool'},
        ],
        'description': 'Try to detect (broadcast) others nodes in the network'
    },
    
    do_show_threads   : {
        'keywords'   : ['agent', 'show-threads'],
        'args'       : [],
        'description': 'List all internal threads of the agent.'
    },
    
    do_follow_log     : {
        'keywords'   : ['agent', 'follow-log'],
        'args'       : [
            {'name': '--part', 'default': '', 'description': 'Follow log part (with debug)'},
        ],
        'description': 'Show info af a daemon'
    },
    
    do_list_follow_log: {
        'keywords'   : ['agent', 'list-follow-log'],
        'args'       : [
        ],
        'description': 'List available logs parts to follow'
    },
}
