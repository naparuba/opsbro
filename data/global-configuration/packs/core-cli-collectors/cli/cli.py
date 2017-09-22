#!/usr/bin/env python

# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com



import sys
import json


from opsbro.log import cprint, logger
from opsbro.unixclient import get_request_errors
from opsbro.cli import get_opsbro_json, print_info_title
from opsbro.collectormanager import collectormgr
from opsbro.library import libstore


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
        logger.do_debug('ERROR: data %d is not managed: prefix=%s' % (str(d), prefix))


def pretty_print(d):
    results = d.get('results')
    del d['results']
    del d['metrics']
    
    flat_results = []
    _extract_data_from_results(results, '', flat_results)
    
    # for pretty print in color, need to have both pygments and don't
    # be in a | or a file dump >, so we need to have a tty ^^
    pygments = libstore.get_pygments()
    if pygments and sys.stdout.isatty():
        lexer = pygments.lexers.get_lexer_by_name("json", stripall=False)
        formatter = pygments.formatters.TerminalFormatter()
        code = json.dumps(d, indent=4)
        result = pygments.highlight(code, lexer, formatter)
        print result
    else:
        pprint = libstore.get_pprint()
        pprint.pprint(d)
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


def do_collectors_show(name='', all=False):
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


def do_collectors_list():
    try:
        collectors = get_opsbro_json('/collectors')
    except get_request_errors(), exp:
        logger.error(exp)
        return
    cnames = collectors.keys()
    cnames.sort()
    for cname in cnames:
        d = collectors[cname]
        cprint(cname.ljust(15) + ':', end='')
        if d['active']:
            cprint('enabled', color='green')
        else:
            cprint('disabled', color='grey')


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


exports = {
    do_collectors_show: {
        'keywords'   : ['collectors', 'show'],
        'args'       : [
            {'name': 'name', 'default': '', 'description': 'Show a specific'},
            {'name': '--all', 'default': False, 'description': 'Show all collectors, even diabled one', 'type': 'bool'},
        ],
        'description': 'Show collectors informations'
    },
    
    do_collectors_list: {
        'keywords'   : ['collectors', 'list'],
        'args'       : [
        ],
        'description': 'Show collectors list'
    },
    
    do_collectors_run : {
        'keywords'   : ['collectors', 'run'],
        'args'       : [
            {'name': 'name', 'description': 'Show a specific'},
        ],
        'description': 'Run a collector'
    },
    
}
