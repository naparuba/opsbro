#!/usr/bin/env python

# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com



import sys
import json
# try pygments for pretty printing if available
from pprint import pprint

try:
    import pygments
    import pygments.lexers
    import pygments.formatters
except ImportError:
    pygments = None

from kunai.log import cprint, logger
from kunai.unixclient import get_json, get_local, request_errors
from kunai.cli import get_kunai_json, get_kunai_local, print_info_title, print_2tab
from kunai.collectormanager import collectormgr


def pretty_print(d):
    # for pretty print in color, need to have both pygments and don't
    # be in a | or a file dump >, so we need to have a tty ^^
    if pygments and sys.stdout.isatty():
        lexer = pygments.lexers.get_lexer_by_name("json", stripall=False)
        formatter = pygments.formatters.TerminalFormatter()
        code = json.dumps(d, indent=4)
        result = pygments.highlight(code, lexer, formatter)
        print result
    else:
        pprint(d)


def do_collectors_show(name='', all=False):
    try:
        collectors = get_kunai_json('/collectors')
    except request_errors, exp:
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
        collectors = get_kunai_json('/collectors')
    except request_errors, exp:
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
        logger.debug('COLLECTOR: launching collector %s' % colname, part='check')
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
