#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com


import sys
import time

from opsbro.log import cprint, logger
from opsbro.unixclient import get_request_errors
from opsbro.cli import get_opsbro_json, print_info_title, AnyAgent
from opsbro.cli_display import print_h1
from opsbro.collectormanager import collectormgr
from opsbro.characters import CHARACTERS

COLLECTORS_STATE_COLORS = {'OK': 'green', 'ERROR': 'red', 'NOT-ELIGIBLE': 'grey', 'RUNNING': 'grey'}


def _extract_data_from_results(d, prefix, res):
    if isinstance(d, dict):
        for (k, v) in d.iteritems():
            _extract_data_from_results(v, prefix + '.' + k, res)
            continue
    elif isinstance(d, list) or isinstance(d, set):
        _idx = 0
        for v in d:
            _extract_data_from_results(v, prefix + '.%d' % _idx, res)
            _idx += 1
    elif isinstance(d, int) or isinstance(d, float) or isinstance(d, basestring) or d is None:
        res.append((prefix, d))
    else:
        logger.do_debug('ERROR: data %s is not managed: prefix=%s' % (str(d), prefix))


def pretty_print(d):
    results = d.get('results')
    del d['results']
    del d['metrics']
    
    flat_results = []
    _extract_data_from_results(results, '', flat_results)
    
    __print_collector_state(d)
    
    if len(flat_results) == 0:
        print "No collector data"
        return
    
    max_prefix_size = max([len(prefix) for (prefix, v) in flat_results])
    flat_results = sorted(flat_results, key=lambda x: x[0])
    print "* Collector data:"
    for (prefix, v) in flat_results:
        cprint('collector.%s' % (d['name']), color='grey', end='')
        cprint('%s' % prefix.ljust(max_prefix_size), color='blue', end='')
        cprint(' = ', end='')
        cprint('%s' % (v), color='magenta')


def __print_collector_state(collector):
    state = collector['state']
    log = collector['log']
    name = collector['name']
    color = COLLECTORS_STATE_COLORS.get(state)
    cprint(' * ', end='')
    cprint('%s' % name.ljust(20), color='magenta', end='')
    cprint(' %s ' % CHARACTERS.arrow_left, end='')
    cprint(state, color=color)
    if log:
        cprint('   | %s' % log, color='grey')


def do_collectors_show(name='', all=False):
    # We need an agent for this
    with AnyAgent():
        try:
            collectors = get_opsbro_json('/collectors')
        except get_request_errors(), exp:
            logger.error(exp)
            return
        
        disabled = []
        for (cname, d) in collectors.iteritems():
            if name and not name == cname:
                continue
            if not name and not d['active'] and not all:
                disabled.append(d)
                continue
            print_info_title('Collector %s' % cname)
            pretty_print(d)
        if len(disabled) > 0:
            print_info_title('Disabled collectors')
            cprint(','.join([d['name'] for d in disabled]), color='grey')


def do_collectors_state():
    # We need an agent for this
    with AnyAgent():
        print_h1('Collectors')
        try:
            collectors = get_opsbro_json('/collectors')
        except get_request_errors(), exp:
            logger.error(exp)
            return
        cnames = collectors.keys()
        cnames.sort()
        for cname in cnames:
            d = collectors[cname]
            __print_collector_state(d)


def do_collectors_run(name):
    collectormgr.load_collectors({})
    for (colname, e) in collectormgr.collectors.iteritems():
        colname = e['name']
        if colname != name:
            continue
        logger.debug('Launching collector', name)
        inst = e['inst']
        logger.debug('COLLECTOR: launching collector %s' % colname)
        inst.main()
        pretty_print(e['results'])


def do_collectors_wait_ok(collector_name, timeout=30):
    import itertools
    spinners = itertools.cycle(CHARACTERS.spinners)
    
    # We need an agent for this
    with AnyAgent():
        current_state = 'PENDING'
        for i in xrange(timeout):
            try:
                collectors = get_opsbro_json('/collectors')
            except get_request_errors(), exp:
                logger.error(exp)
                return
            collector = None
            for (cname, c) in collectors.iteritems():
                if cname == collector_name:
                    collector = c
            if not collector:
                logger.error("Cannot find the collector '%s'" % collector_name)
                sys.exit(2)
            current_state = collector['state']
            cprint('\r %s ' % spinners.next(), color='blue', end='')
            cprint('%s' % collector_name, color='magenta', end='')
            cprint(' is ', end='')
            cprint('%15s ' % current_state, color=COLLECTORS_STATE_COLORS.get(current_state, 'cyan'), end='')
            cprint(' (%d/%d)' % (i, timeout), end='')
            # As we did not \n, we must flush stdout to print it
            sys.stdout.flush()
            if current_state == 'OK':
                cprint("\nThe collector %s is OK" % collector_name)
                sys.exit(0)
            logger.debug("Current state %s" % current_state)
            
            time.sleep(1)
        cprint("\nThe collector %s is not OK after %s seconds (currently %s)" % (collector_name, timeout, current_state))
        sys.exit(2)


exports = {
    do_collectors_show   : {
        'keywords'   : ['collectors', 'show'],
        'args'       : [
            {'name': 'name', 'default': '', 'description': 'Show a specific'},
            {'name': '--all', 'default': False, 'description': 'Show all collectors, even diabled one', 'type': 'bool'},
        ],
        'description': 'Show collectors informations'
    },
    
    do_collectors_state  : {
        'keywords'   : ['collectors', 'state'],
        'args'       : [
        ],
        'description': 'Show collectors state'
    },
    
    do_collectors_run    : {
        'keywords'   : ['collectors', 'run'],
        'args'       : [
            {'name': 'name', 'description': 'Show a specific'},
        ],
        'description': 'Run a collector'
    },
    
    do_collectors_wait_ok: {
        'keywords'   : ['collectors', 'wait-ok'],
        'args'       : [
            {'name': 'collector-name', 'description': 'Name of the collector rule to wait for OK state'},
            {'name': '--timeout', 'type': 'int', 'default': 30, 'description': 'Timeout to let the initialization'},
        ],
        'description': 'Wait until the collector rule is in OK state'
    },
    
}
