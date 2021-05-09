#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

from __future__ import print_function
import sys
import base64
import uuid
import time
import os
import sys

if os.name == 'nt':
    try:
        import win32serviceutil
        import win32api
    except ImportError:  # missing lib, must launc hthe setup.py
        win32serviceutil = win32api = None

from opsbro.characters import CHARACTERS
from opsbro.log import cprint, logger, sprintf
from opsbro.misc.lolcat import lolcat
from opsbro.launcher import Launcher
from opsbro.unixclient import get_request_errors
from opsbro.cli import get_opsbro_json, get_opsbro_local, print_info_title, print_2tab, CONFIG, wait_for_agent_started, DEFAULT_INFO_COL_SIZE
from opsbro.cli_display import print_h1
from opsbro.yamleditor import yml_parameter_get, parameter_add_to_main_yml, parameter_remove_to_main_yml, parameter_set_to_main_yml
from opsbro.defaultpaths import DEFAULT_LOCK_PATH, DEFAULT_CFG_FILE
from opsbro.configurationmanager import configmgr
from opsbro.collectormanager import COLLECTORS_STATE_COLORS, COLLECTORS_STATES
from opsbro.module import TYPES_DESCRIPTIONS, MODULE_STATE_COLORS, MODULE_STATES
from opsbro.topic import TOPICS, TOPICS_LABELS, TOPICS_LABEL_BANNER, MAX_TOPICS_LABEL_SIZE, TOPICS_COLORS, topiker, TOPIC_SERVICE_DISCOVERY, TOPIC_AUTOMATIC_DECTECTION, TOPIC_GENERIC, TOPIC_METROLOGY, TOPIC_MONITORING, TOPIC_SYSTEM_COMPLIANCE, \
    TOPIC_CONFIGURATION_AUTOMATION
from opsbro.monitoring import CHECK_STATES, STATE_ID_COLORS, STATE_COLORS
from opsbro.compliancemgr import ALL_COMPLIANCE_STATES, COMPLIANCE_STATE_COLORS
from opsbro.generator import GENERATOR_STATES, GENERATOR_STATE_COLORS
from opsbro.util import my_cmp, my_sort, bytes_to_unicode

NO_ZONE_DEFAULT = '(no zone)'


############# ********************        MEMBERS management          ****************###########


def __call_service_handler():
    def __ctrlHandler(ctrlType):
        return True
    
    
    from opsbro.windows_service.windows_service import Service
    win32api.SetConsoleCtrlHandler(__ctrlHandler, True)
    win32serviceutil.HandleCommandLine(Service)


def do_service_install():
    # hack argv for the install
    sys.argv = ['c:\\opsbro\\bin\\opsbro', 'install']
    if win32api is None or win32serviceutil is None:
        cprint('ERROR: missing win32 librairy, you must call setup.py install first', color='red')
        sys.exit(2)
    __call_service_handler()


def do_service_remove():
    # hack argv for the remove
    sys.argv = ['c:\\opsbro\\bin\\opsbro', 'remove']
    __call_service_handler()


def __print_topic_header(TOPIC_ID):
    topic_color = TOPICS_COLORS[TOPIC_ID]
    picto = u'%s%s %s' % (CHARACTERS.corner_top_left, CHARACTERS.hbar * 19, TOPICS_LABELS[TOPIC_ID])
    cprint(lolcat.get_line(picto, topic_color, spread=None))


def __print_topic_picto(topic):
    # topic_color = TOPICS_COLORS[topic]
    # picto = u'%s ' % CHARACTERS.vbar
    # cprint(lolcat.get_line(picto, topic_color, spread=None), end='')
    cprint(' ', end='')


def __print_key_val(key, value, color='green', topic=None, end_line=True):
    if topic is None:
        cprint((' - %s: ' % key).ljust(DEFAULT_INFO_COL_SIZE), end='', color='blue')
    else:
        __print_topic_picto(topic)
        cprint(('%s: ' % key).ljust(DEFAULT_INFO_COL_SIZE - 2), end='', color='blue')
    if end_line:
        cprint(value, color=color)
    else:
        cprint(value, color=color, end='')


def __print_note(s):
    cprint('  %s Note: %s' % (CHARACTERS.corner_bottom_left, s), color='grey')


def __print_more(s):
    cprint('  %s More %s          %s' % (CHARACTERS.corner_bottom_left, CHARACTERS.arrow_left, s), color='grey')


def do_info(show_logs):
    try:
        d = get_opsbro_json('/agent/info')
    except get_request_errors() as exp:
        logger.error('Cannot join opsbro agent for info: %s' % exp)
        sys.exit(1)
    logs = d.get('logs')
    version = d.get('version')
    cpu_consumption = d.get('cpu_consumption')
    memory_consumption = d.get('memory_consumption')
    name = d.get('name')
    display_name = d.get('display_name', '')
    # A failback to display name is the name (hostname)
    if not display_name:
        display_name = name
    else:  # show it's a display name
        display_name = '[ ' + display_name + ' ]'
    port = d.get('port')
    local_addr = d.get('local_addr')
    public_addr = d.get('public_addr')
    zone = d.get('zone')
    zone_color = 'green'
    if not zone:
        zone = NO_ZONE_DEFAULT
        zone_color = 'red'
    
    is_managed_system = d.get('is_managed_system')
    system_distro = d.get('system_distro')
    system_distroversion = d.get('system_distroversion')
    
    is_zone_protected = d.get('is_zone_protected')
    is_zone_protected_display = ('%s zone have a gossip key' % CHARACTERS.check, 'green') if is_zone_protected else ('%s zone do not have a gossip key' % CHARACTERS.double_exclamation, 'yellow')
    
    nb_threads = d.get('threads')['nb_threads']
    hosting_drivers_state = d.get('hosting_drivers_state', [])
    httpservers = d.get('httpservers', {'internal': None, 'external': None})
    socket_path = d.get('socket')
    _uuid = d.get('uuid')
    # Modules groking
    modules = d.get('modules', {})
    topics = d.get('topics', {})
    # Get groups as sorted
    groups = d.get('groups')
    groups.sort()
    groups = ','.join(groups)
    collectors = d.get('collectors')
    monitoring = d.get('monitoring')
    compliance = d.get('compliance')
    generators = d.get('generators')
    kv_store = d.get('kv')
    have_fast_yaml = d.get('have_fast_yaml')
    
    ################### Generic
    __print_topic_header(TOPIC_GENERIC)
    # print_info_title('OpsBro Daemon')
    
    __print_key_val('Name', name, topic=TOPIC_GENERIC)
    display_name_color = 'green' if (name != display_name) else 'grey'
    __print_key_val('Display name', display_name, color=display_name_color, topic=TOPIC_GENERIC)
    
    __print_key_val('System', '%s (version %s) ' % (system_distro, system_distroversion), color='green', topic=TOPIC_GENERIC, end_line='')
    if is_managed_system:
        cprint(' %s managed' % CHARACTERS.check, color='grey')
    else:
        cprint(' %s this system is not managed' % CHARACTERS.double_exclamation, color='yellow')
        __print_more(' Not managed means that configuration automation & system compliance will not be available')
    
    # We will print modules by modules types
    # cprint(' - Modules: '.ljust(DEFAULT_INFO_COL_SIZE), end='', color='blue')
    modules_by_states = {}
    for module_state in MODULE_STATES:
        modules_by_states[module_state] = []
    for (module_name, module) in modules.items():
        modules_by_states[module['state']].append(module)
    
    strs = []
    for module_state in MODULE_STATES:
        nb = len(modules_by_states[module_state])
        state_color = MODULE_STATE_COLORS.get(module_state, 'grey')
        color = 'grey' if nb == 0 else state_color
        _s = sprintf('%d %s ' % (nb, module_state), color=color, end='')
        strs.append(_s)
    module_string = sprintf(' / ', color='grey', end='').join(strs)
    
    __print_key_val('Modules', module_string, topic=TOPIC_GENERIC)
    
    __print_topic_picto(TOPIC_GENERIC)
    __print_more('opsbro agent modules state')
    
    ################### Service Discovery
    cprint('')
    __print_topic_header(TOPIC_SERVICE_DISCOVERY)
    
    __print_key_val('UUID', _uuid, topic=TOPIC_SERVICE_DISCOVERY)
    __print_key_val('Local addr', local_addr, topic=TOPIC_SERVICE_DISCOVERY)
    __print_key_val('Public addr', public_addr, topic=TOPIC_SERVICE_DISCOVERY)
    
    __print_key_val('UDP port', port, topic=TOPIC_SERVICE_DISCOVERY)
    
    # Normal agent information
    ext_server = httpservers.get('external')
    int_server = httpservers.get('internal')
    ext_threads = '%d/%d' % (ext_server['nb_threads'] - ext_server['idle_threads'], ext_server['nb_threads'])
    if int_server:
        int_threads = '%d/%d' % (int_server['nb_threads'] - int_server['idle_threads'], int_server['nb_threads'])
    else:  # windows case
        int_threads = '(not available on windows)'
    
    __print_key_val('HTTP threads', 'LAN:%s                        Private socket:%s' % (ext_threads, int_threads), topic=TOPIC_SERVICE_DISCOVERY)
    __print_topic_picto(TOPIC_SERVICE_DISCOVERY)
    __print_note('          Listen on the TCP port %s     Listen on the unix socket %s' % (port, socket_path))
    
    __print_key_val('Zone', zone, color=zone_color, topic=TOPIC_SERVICE_DISCOVERY, end_line=False)
    cprint(' (%s)' % is_zone_protected_display[0], color=is_zone_protected_display[1])
    __print_topic_picto(TOPIC_SERVICE_DISCOVERY)
    __print_more('opsbro gossip members')
    
    ################################## Automatic Detection
    cprint('')
    __print_topic_header(TOPIC_AUTOMATIC_DECTECTION)
    __print_key_val('Groups', groups, topic=TOPIC_AUTOMATIC_DECTECTION)
    
    __print_topic_picto(TOPIC_AUTOMATIC_DECTECTION)
    __print_more('opsbro detectors state')
    
    # Show hosting drivers, and why we did chose this one
    main_driver_founded = False
    strs = []
    for driver_entry in hosting_drivers_state:
        driver_name = driver_entry['name']
        driver_is_active = driver_entry['is_active']
        _name = driver_name
        if not main_driver_founded and driver_is_active:
            strs.append(sprintf('[', color='magenta') + sprintf(_name, color='green') + sprintf(']', color='magenta'))
            main_driver_founded = True
        elif driver_is_active:
            strs.append(sprintf(_name, color='green'))
        else:
            strs.append(sprintf(_name, color='grey'))
    
    _hosting_drivers_state_string = sprintf(' %s ' % CHARACTERS.arrow_left, color='grey').join(strs)
    __print_key_val('Hosting drivers', _hosting_drivers_state_string, topic=TOPIC_AUTOMATIC_DECTECTION)
    __print_topic_picto(TOPIC_AUTOMATIC_DECTECTION)
    __print_note('first founded valid driver is used as main hosting driver (give uuid, public/private ip, %s)' % CHARACTERS.three_dots)
    
    ################################## Monitoring
    cprint('')
    __print_topic_header(TOPIC_MONITORING)
    
    monitoring_strings = []
    for check_state in CHECK_STATES:
        count = monitoring[check_state]
        color = STATE_COLORS.get(check_state) if count != 0 else 'grey'
        s = ('%d %s' % (count, check_state.upper())).ljust(15)
        s = sprintf(s, color=color, end='')
        monitoring_strings.append(s)
    monitoring_string = sprintf(' / ', color='grey', end='').join(monitoring_strings)
    __print_key_val('Check states', monitoring_string, topic=TOPIC_MONITORING)
    __print_topic_picto(TOPIC_MONITORING)
    __print_more('opsbro monitoring state')
    
    ################################## Metrology
    # Now collectors part
    cprint('')
    __print_topic_header(TOPIC_METROLOGY)
    cnames = list(collectors.keys())
    cnames.sort()
    collectors_states = {}
    for collector_state in COLLECTORS_STATES:
        collectors_states[collector_state] = []
    for cname in cnames:
        v = collectors[cname]
        collector_state = v['state']
        collectors_states[collector_state].append(cname)
    
    strs = []
    for collector_state in COLLECTORS_STATES:
        nb = len(collectors_states[collector_state])
        state_color = COLLECTORS_STATE_COLORS.get(collector_state, 'grey')
        color = 'grey' if nb == 0 else state_color
        _s = ('%d %s' % (nb, collector_state)).ljust(15)
        _s = sprintf(_s, color=color, end='')
        strs.append(_s)
    collector_string = sprintf(' / ', color='grey', end='').join(strs)
    __print_key_val('Collectors', collector_string, topic=TOPIC_METROLOGY)
    __print_topic_picto(TOPIC_METROLOGY)
    __print_more('opsbro collectors state')
    
    ################################## configuration automation
    cprint('')
    __print_topic_header(TOPIC_CONFIGURATION_AUTOMATION)
    
    strs = []
    for state in GENERATOR_STATES:
        nb = generators[state]
        state_color = GENERATOR_STATE_COLORS.get(state, 'grey')
        color = 'grey' if nb == 0 else state_color
        _s = ('%d %s' % (nb, state)).ljust(15)
        _s = sprintf(_s, color=color, end='')
        strs.append(_s)
    generator_string = sprintf(' / ', color='grey', end='').join(strs)
    __print_key_val('Generators', generator_string, topic=TOPIC_CONFIGURATION_AUTOMATION)
    __print_topic_picto(TOPIC_CONFIGURATION_AUTOMATION)
    __print_more('opsbro generators state')
    
    ################################## system compliance
    cprint('')
    __print_topic_header(TOPIC_SYSTEM_COMPLIANCE)
    
    strs = []
    for state in ALL_COMPLIANCE_STATES:
        nb = compliance[state]
        state_color = COMPLIANCE_STATE_COLORS.get(state, 'grey')
        color = 'grey' if nb == 0 else state_color
        _s = ('%d %s' % (nb, state)).ljust(15)
        _s = sprintf(_s, color=color, end='')
        strs.append(_s)
    collector_string = sprintf(' / ', color='grey', end='').join(strs)
    __print_key_val('Compliance rules', collector_string, topic=TOPIC_SYSTEM_COMPLIANCE)
    __print_topic_picto(TOPIC_SYSTEM_COMPLIANCE)
    __print_more('opsbro compliance state')
    
    ############### Logs:  Show errors logs if any
    cprint('')
    print_info_title('Technical info')
    
    cprint(' - Job threads: '.ljust(DEFAULT_INFO_COL_SIZE), end='', color='blue')
    cprint(nb_threads, color='green')
    
    if memory_consumption != 0:
        mo_memory_consumption = int(memory_consumption / 1024.0 / 1024.0)
        s = '%dMB' % mo_memory_consumption
        __print_key_val('Memory usage', s)
    
    if cpu_consumption != 0:
        s = '%.1f%%' % cpu_consumption
        __print_key_val('CPU Usage', s)
        __print_more('opsbro agent internal show-threads')
    
    kv_store_backend = kv_store.get('backend', None)
    if kv_store_backend:
        cprint(' - KV Backend: '.ljust(DEFAULT_INFO_COL_SIZE), end='', color='blue')
        cprint(kv_store_backend['name'], color='green')
        cprint('    - size: '.ljust(DEFAULT_INFO_COL_SIZE), end='', color='blue')
        cprint('%.2fMB' % (kv_store['stats']['size'] / 1024.0 / 1024.0), color='green')
        
        if kv_store_backend['name'] != 'leveldb':
            __print_note('You do not have the fastest lib/backend. Please launch the command: opsbro compliance launch "Install tuning libs" --timeout 120')
        
        kv_store_error = kv_store['stats']['error']
        if kv_store_error != '':
            cprint('    - error: '.ljust(DEFAULT_INFO_COL_SIZE), color='blue', end='')
            cprint(kv_store_error, color='red')
    
    # Warn if we are missing the yaml lib, because it cause a very poor launch
    cprint(' - Fast Yaml: '.ljust(DEFAULT_INFO_COL_SIZE), end='', color='blue')
    if not have_fast_yaml:
        cprint('MISSING', color='yellow')
        __print_note('you should install the python-yaml lib')
    else:
        cprint('OK', color='green')
    
    cprint(' - Version: '.ljust(DEFAULT_INFO_COL_SIZE), end='', color='blue')
    cprint(version, color='green')
    
    errors = logs.get('ERROR')
    warnings = logs.get('WARNING')
    
    cprint(' - Logs: '.ljust(DEFAULT_INFO_COL_SIZE), end='', color='blue')
    # Put warning and errors in red/yellow if need only
    error_color = 'red' if len(errors) > 0 else 'grey'
    warning_color = 'yellow' if len(warnings) > 0 else 'grey'
    cprint('%d errors    ' % len(errors), color=error_color, end='')
    cprint('%d warnings   ' % len(warnings), color=warning_color)
    
    # If there are errors or warnings, help the user to know it can print them
    if not show_logs and (len(errors) > 0 or len(warnings) > 0):
        __print_note('you can show error & warning logs with the --show-logs options')
    
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


def do_node_uuid():
    try:
        d = get_opsbro_json('/agent/info')
    except get_request_errors() as exp:
        logger.error('Cannot join opsbro agent for info: %s' % exp)
        sys.exit(1)
    _uuid = d.get('uuid')
    cprint(_uuid)


def do_node_local_addr():
    try:
        d = get_opsbro_json('/agent/info')
    except get_request_errors() as exp:
        logger.error('Cannot join opsbro agent for info: %s' % exp)
        sys.exit(1)
    local_addr = d.get('local_addr')
    cprint(local_addr)


def do_node_public_addr():
    try:
        d = get_opsbro_json('/agent/info')
    except get_request_errors() as exp:
        logger.error('Cannot join opsbro agent for info: %s' % exp)
        sys.exit(1)
    public_addr = d.get('public_addr')
    cprint(public_addr)


def do_modules_state():
    try:
        d = get_opsbro_json('/agent/info')
    except get_request_errors() as exp:
        logger.error('Cannot join opsbro agent for module state: %s' % exp)
        sys.exit(1)
    modules = d.get('modules', {})
    print_info_title('Modules')
    modules_types = {}
    for (module_name, module) in modules.items():
        module_type = module['module_type']
        if module_type not in modules_types:
            modules_types[module_type] = {}
        modules_types[module_type][module_name] = module
    
    modules_type_names = list(modules_types.keys())
    modules_type_names.sort()
    
    for (module_type, _modules) in modules_types.items():
        cprint(' - [', end='')
        cprint(' %-10s ' % module_type.capitalize(), color='magenta', end='')
        cprint(' ]: ', end='')
        cprint(TYPES_DESCRIPTIONS.get(module_type, 'unknown module type'), color='grey')
        
        module_names = list(_modules.keys())
        module_names.sort()
        for module_name in module_names:
            module = _modules[module_name]
            state = module['state']
            state_color = MODULE_STATE_COLORS.get(state, 'grey')
            log = module['log']
            kwcolor = {'color': 'grey'} if state == 'DISABLED' else {}
            cprint('     * ', end='', **kwcolor)
            cprint('%-20s ' % module_name, color=state_color, end='')
            cprint(state, color=state_color)
            if state != 'DISABLED' and log:
                cprint('       | Log: %s' % log, color='grey')
    cprint(' | Note: you can look at modules configuration with the command  opsbro packs show', color='grey')


# Main daemon function. Currently in blocking mode only
def do_start(daemon, cfg_dir, one_shot, auto_detect):
    if daemon and one_shot:
        logger.error('The parameters --daemon and --one-shot are not compatible.')
        sys.exit(2)
    
    cprint('Starting opsbro daemon', color='green')
    lock_path = CONFIG.get('lock', DEFAULT_LOCK_PATH)
    l = Launcher(lock_path=lock_path, cfg_dir=cfg_dir)
    
    # We did skip some configuration/objects load to boost CLI load, so do this now
    l.finish_to_load_configuration_and_objects()
    
    # If we must go daemon and manage process things, do it now
    # NOTE: only the last son process reach the start/main function
    l.do_daemon_init_and_start(is_daemon=daemon, one_shot=one_shot, force_wait_proxy=auto_detect)


def do_stop():
    try:
        (code, r) = get_opsbro_local('/stop')
    except get_request_errors() as exp:
        logger.error(exp)
        return
    cprint(r, color='green')


def do_keygen():
    k = uuid.uuid1().hex[:16]
    cprint('UDP Encryption key: (aka encryption_key)', end='')
    cprint(base64.b64encode(k), color='green')
    cprint('')
    try:
        import rsa
    except ImportError:
        logger.error('Missing python-rsa module for RSA keys generation, please install it')
        return
    pubkey, privkey = rsa.newkeys(2048)
    
    cprint("Private RSA key (2048). (aka master_key_priv for for file mfkey.priv)")
    s_privkey = privkey.save_pkcs1()
    cprint(s_privkey, color='green')
    cprint('')
    cprint("Public RSA key (2048). (aka master_key_pub for file mfkey.pub)")
    s_pubkey = pubkey.save_pkcs1()
    cprint(s_pubkey, color='green')
    cprint('')


# Sort threads by user time, if same, sort by name
def _sort_threads(t1, t2):
    t1_cpu = t1['user_time']
    t2_cpu = t2['user_time']
    t1_name = t1['name']
    t2_name = t2['name']
    if t1_cpu == t2_cpu:
        return my_cmp(t1_name, t2_name)
    else:  # bigger first
        return -my_cmp(t1_cpu, t2_cpu)


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
    except get_request_errors() as exp:
        logger.error('Cannot join opsbro agent to show threads: %s' % exp)
        sys.exit(1)
    all_threads = data['threads']
    process = data['process']
    age = data['age']
    
    got_values = False
    for t in all_threads:
        if t['user_time'] != -1:
            got_values = True
    
    if not got_values:
        cprint('You do not have the psutil lib installed. Please launch the command: opsbro compliance launch "Install tuning libs" --timeout 120', color='red')
        sys.exit(2)
    
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
    for (pname, e) in threads_into_parts.items():
        e['threads'] = my_sort(e['threads'], cmp_f=_sort_threads)
    
    # Now have parts sort by their times (from bigger to min)
    parts_sorts_by_cpu_usage = threads_into_parts.values()
    parts_sorts_by_cpu_usage = sorted(parts_sorts_by_cpu_usage, key=lambda e: -e['user_time'])
    
    # Then by name
    parts_sorts_by_name = threads_into_parts.values()
    parts_sorts_by_name = sorted(parts_sorts_by_name, key=lambda e: e['name'])
    
    all_not_daemon_threads = my_sort(all_not_daemon_threads, cmp_f=_sort_threads)
    
    upercent, syspercent = __get_cpu_time_percent_display(process, age)
    cprint('Total process CPU consumption:  ', color='blue', end='')
    cprint('cpu(user):%s%%  ' % upercent, color='magenta', end='')
    cprint('cpu(system):%s%%' % syspercent)
    cprint("\n")
    
    cprint("Summary of CPU consumption based on opsbro parts:")
    for p in parts_sorts_by_cpu_usage:
        upercent, syspercent = __get_cpu_time_percent_display(p, age)
        cprint('  * [ ', end='')
        cprint('%-15s' % p['name'], color='blue', end='')
        cprint(' ]  ', end='')
        cprint('cpu(user):%s%%  ' % upercent, color='magenta', end='')
        cprint('cpu(system):%s%%' % syspercent)
    cprint("")
    cprint("Daemon threads (persistent):")
    for p in parts_sorts_by_name:
        cprint('[ ', end='')
        cprint('%-15s' % p['name'], color='blue', end='')
        cprint(' ]  ')
        for t in p['threads']:
            upercent, syspercent = __get_cpu_time_percent_display(t, age)
            cprint('   * %-55s  thread id:%5d   cpu(user):%s%%   cpu(system):%s%%' % (t['name'], t['tid'], upercent, syspercent))
    if all_not_daemon_threads:
        cprint("\nTemporary threads:")
        for t in all_not_daemon_threads:
            upercent, syspercent = __get_cpu_time_percent_display(t, age)
            cprint('   Name:%-55s  id:%d   cpu(user):%s%%   cpu(system):%s%%' % (t['name'], t['tid'], upercent, syspercent))


def do_list_follow_log():
    try:
        parts = get_opsbro_json('/log/parts/')
    except get_request_errors() as exp:
        logger.error('Cannot join opsbro agent to list logs: %s' % exp)
        sys.exit(1)
    parts.sort()
    cprint("Available parts to follow logs:")
    for p in parts:
        cprint("  * %s" % p)


def do_follow_log(part=''):
    if not part:
        return
    try:
        import fcntl
    except ImportError:
        cprint("Error: this action is not availabe on your OS.")
        return
    
    cprint('Try to follow log part %s' % part)
    p = '/tmp/opsbro-follow-%s' % part
    
    # Clean fifo to be sure to clean previous runs
    if os.path.exists(p):
        os.unlink(p)
    
    if not os.path.exists(p):
        os.mkfifo(p)
    
    colors = {'DEBUG': 'magenta', 'INFO': 'blue', 'WARNING': 'yellow', 'ERROR': 'red'}
    try:
        w = 0.001
        must_loop = True
        while must_loop:
            try:
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
                            for (k, color) in colors.items():
                                if k in line:
                                    cprint(line, color=color)
                                    already_print = True
                                    break
                            if not already_print:
                                cprint(line)
            except KeyboardInterrupt:
                must_loop = False
    finally:
        try:
            cprint("\nDisabling log dumping for the part %s" % part)
            os.unlink(p)
        except:
            pass


def do_agent_parameters_show():
    logger.setLevel('ERROR')
    # We should already have load the configuration, so just dump it
    # now we read them, set it in our object
    parameters_from_local_configuration = configmgr.get_parameters_for_cluster_from_configuration()
    # print "Local parameters", parameters_from_local_configuration
    print_h1('Local agent parameters')
    key_names = list(parameters_from_local_configuration.keys())
    key_names.sort()
    for k in key_names:
        v = parameters_from_local_configuration[k]
        cprint('  * ', end='')
        cprint('%-15s' % k, color='magenta', end='')
        cprint(' %s ' % CHARACTERS.arrow_left, end='')
        cprint('%s\n' % v, color='green', end='')


def do_agent_parameters_set(parameter_name, str_value):
    str_value = bytes_to_unicode(str_value)  # always be sure than we manage unicode here
    parameter_set_to_main_yml(parameter_name, str_value)


def do_agent_parameters_get(parameter_name):
    parameters_file_path = DEFAULT_CFG_FILE
    
    yml_parameter_get(parameters_file_path, parameter_name, file_display='agent.%s' % parameter_name)
    cprint('NOTE: only the yml configuration file is modified. You need to restart your agent to use this modification', color='grey')
    return


def do_agent_parameters_add(parameter_name, str_value):
    parameter_add_to_main_yml(parameter_name, str_value)


def do_agent_parameters_remove(parameter_name, str_value):
    parameter_remove_to_main_yml(parameter_name, str_value)


def _show_init_d_label():
    cprint('\rStarting ', color='magenta', end='')
    cprint('Ops', color='blue', end='')
    cprint('*', color='white', end='')
    cprint('Bro', color='red', end='')
    cprint(':', end='')


def _print_move_to_init_d_state():
    cprint('\033[60G', end='')


# We are waiting for the agent to start. We have 3 modes based on the show_init_header
# False (default): call by cli script, will display a text helping the user to
#                  understand what is the current state of the daemon
# True           : used by the init.d script, will display the init.d header
def do_agent_wait_full_initialized(timeout=30, show_init_header=False):
    import itertools
    from opsbro.agentstates import AGENT_STATES
    
    if show_init_header:
        spinners = itertools.cycle(CHARACTERS.spinners)
        display_state = AGENT_STATES.AGENT_STATE_INITIALIZING
        agent_state = display_state
        for i in range(timeout):
            _show_init_d_label()
            _print_move_to_init_d_state()
            cprint('[', end='')
            cprint('%s ' % next(spinners), color='cyan', end='')  # note: spinners.next() do not exists in python3
            cprint(display_state, color='blue', end='')
            cprint(']', end='')
            sys.stdout.flush()
            agent_state = wait_for_agent_started(visual_wait=False, timeout=1, wait_for_spawn=True)
            
            # If the agent is started, we can exit and show the user help
            if agent_state == AGENT_STATES.AGENT_STATE_OK:
                _show_init_d_label()
                _print_move_to_init_d_state()
                cprint('[', end='')
                cprint('%s OK' % CHARACTERS.check, color='green', end='')
                cprint(']           ')  # lot of space to clean the initializing text
                cprint('  %s Note: you can have information about OpsBro with the command: opsbro agent info' % CHARACTERS.corner_bottom_left, color='grey')
                return
            # if stopped or initializing, still wait
            elif agent_state in [AGENT_STATES.AGENT_STATE_STOPPED, AGENT_STATES.AGENT_STATE_INITIALIZING]:
                continue
            else:
                cprint('ERROR: the agent state: %s is not managed' % agent_state, color='red')
                sys.exit(2)
        # Oups, timeout reached, still not initialized after this
        _show_init_d_label()
        _print_move_to_init_d_state()
        cprint('FAILED (initialisation was not finish after %d seconds): %s' % (timeout, agent_state), color='red')
        sys.exit(2)
    else:
        agent_state = wait_for_agent_started(visual_wait=True, timeout=timeout, wait_for_spawn=True)
        if agent_state == AGENT_STATES.AGENT_STATE_OK:
            cprint(AGENT_STATES.AGENT_STATE_OK, color='green')
            return
        if agent_state == AGENT_STATES.AGENT_STATE_STOPPED:
            cprint(AGENT_STATES.AGENT_STATE_STOPPED, color='red')
            sys.exit(2)
        if agent_state == AGENT_STATES.AGENT_STATE_INITIALIZING:
            cprint(AGENT_STATES.AGENT_STATE_INITIALIZING, color='yellow')
            sys.exit(2)
        cprint(agent_state, color='grey')


exports = {
    do_start                      : {
        'keywords'   : ['agent', 'start'],
        'args'       : [
            {'name': '--daemon', 'type': 'bool', 'default': False, 'description': 'Start opsbro into the background'},
            {'name': '--cfg-dir', 'default': '/etc/opsbro', 'description': 'Set a specifc configuration file'},
            {'name': '--one-shot', 'type': 'bool', 'default': False, 'description': 'Execute the agent but without slaying alive. It just execute its jobs once, and then exit. Is not compatible with the --daemon parameter.'},
            {'name': '--auto-detect', 'default': False, 'description': 'Lock the daemon startup until at least one proxy node is join. If none is available, loop for auto-detect until a proxy node is detected.', 'type': 'bool'},
        ],
        'description': 'Start the opsbro daemon',
        'examples'   : [
            {
                'title': 'Start as foreground in the shell',
                'args' : ['agent', 'start'],
            },
        ],
    },
    
    do_stop                       : {
        'keywords'   : ['agent', 'stop'],
        'args'       : [],
        'description': 'Stop the opsbro daemon'
    },
    
    do_service_install            : {
        'keywords'   : ['agent', 'windows', 'service-install'],
        'args'       : [],
        'description': 'Install windows service',
        'examples'   : [
            {
                'title': 'Declare the agent as a windows service',
                'args' : ['agent', 'windows', 'service-install'],
            },
        ],
    },
    
    do_service_remove             : {
        'keywords'   : ['agent', 'windows', 'service-remove'],
        'args'       : [],
        'description': 'Remove windows service',
        'examples'   : [
            {
                'title': 'Remove the agent as a windows service',
                'args' : ['agent', 'windows', 'service-remove'],
            },
        ],
    },
    
    do_info                       : {
        'keywords'   : ['agent', 'info'],
        'args'       : [
            {'name': '--show-logs', 'default': False, 'description': 'Dump last warning & error logs', 'type': 'bool'},
        ],
        'need_agent' : True,
        'description': 'Show info af a daemon',
        'examples'   : [
            {
                'title': 'Show main information about the running agent',
                'args' : ['agent', 'info'],
            },
            {
                'title': 'Show info and also last 20 warning and error logs',
                'args' : ['agent', 'info', '--show-logs'],
            },
        
        ],
    },
    
    do_node_uuid                  : {
        'keywords'   : ['agent', 'print', 'uuid'],
        'args'       : [
        ],
        'need_agent' : True,
        'description': 'Print the node uniq uuid'
    },
    
    do_node_local_addr            : {
        'keywords'   : ['agent', 'print', 'local-addr'],
        'args'       : [
        ],
        'need_agent' : True,
        'description': 'Print the node local address'
    },
    
    do_node_public_addr           : {
        'keywords'   : ['agent', 'print', 'public-addr'],
        'args'       : [
        ],
        'need_agent' : True,
        'description': 'Print the node public address'
    },
    
    do_modules_state              : {
        'keywords'   : ['agent', 'modules', 'state'],
        'args'       : [
        ],
        'need_agent' : True,
        'description': 'Show the current state of daemon modules.'
    },
    
    do_keygen                     : {
        'keywords'   : ['agent', 'keygen'],
        'args'       : [],
        'description': 'Generate a encryption key'
    },
    
    do_show_threads               : {
        'keywords'   : ['agent', 'internal', 'show-threads'],
        'args'       : [],
        'need_agent' : True,
        'description': 'List all internal threads of the agent.'
    },
    
    do_follow_log                 : {
        'keywords'   : ['agent', 'log', 'follow'],
        'args'       : [
            {'name': 'part', 'default': '', 'description': 'Follow log part (with debug)'},
        ],
        'need_agent' : True,
        'description': 'Show info af a daemon',
        'examples'   : [
            {
                'title': 'Declare the agent as a windows service',
                'args' : ['agent', 'log', 'follow', 'gossip'],
            },
        ],
    },
    
    do_list_follow_log            : {
        'keywords'   : ['agent', 'log', 'list'],
        'args'       : [
        ],
        'need_agent' : True,
        'description': 'List available logs parts to follow'
    },
    
    do_agent_parameters_show      : {
        'keywords'   : ['agent', 'parameters', 'show'],
        'args'       : [
        ],
        'description': 'Show the agent parameters (pid, ...)'
    },
    
    do_agent_parameters_set       : {
        'keywords'   : ['agent', 'parameters', 'set'],
        'args'       : [
            {'name': 'parameter_name', 'description': 'Parameter name to set'},
            {'name': 'value', 'description': 'Value to set for this parameter'},
        ],
        'description': 'Set a new value to the agent parameter',
        'examples'   : [
            {
                'title': 'Set the node name that will be used by other nodes',
                'args' : ['agent', 'parameters', 'set', 'display_name', 'my-server'],
            },
        ],
    },
    
    do_agent_parameters_get       : {
        'keywords'   : ['agent', 'parameters', 'get'],
        'args'       : [
            {'name': 'parameter_name', 'description': 'Parameter name to get'},
        ],
        'description': 'Get a value from the agent parameter',
        'examples'   : [
            {
                'title': 'Get in whiwh zone the node is',
                'args' : ['agent', 'parameters', 'get', 'zone'],
            },
        ],
        
    },
    
    do_agent_parameters_add       : {
        'keywords'   : ['agent', 'parameters', 'add'],
        'args'       : [
            {'name': 'parameter_name', 'description': 'Parameter name to add a new value'},
            {'name': 'value', 'description': 'Value to set for this parameter'},
        ],
        'description': 'Add a new value to a agent parameter value (must be a list)',
        'examples'   : [
            {
                'title': 'Set the node in the production group',
                'args' : ['agent', 'parameters', 'add', 'groups', 'production'],
            },
        ],
    },
    
    do_agent_parameters_remove    : {
        'keywords'   : ['agent', 'parameters', 'remove'],
        'args'       : [
            {'name': 'parameter_name', 'description': 'Parameter name to remove a value.'},
        ],
        'description': 'Remove a new value to a agent parameter value (must be a list)'
    },
    
    do_agent_wait_full_initialized: {
        'keywords'   : ['agent', 'wait-initialized'],
        'args'       : [
            {'name': '--timeout', 'type': 'int', 'default': 30, 'description': 'Timeout to let the initialization'},
            {'name': '--show-init-header', 'type': 'bool', 'default': False, 'description': '(used by the init.d script) show the init.d header'},
        ],
        'description': 'Wait until the agent is fully initialized (collector, detection, system conpliance are done, etc)'
    },
    
}
