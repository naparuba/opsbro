#!/usr/bin/env python

# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com


import json

# try pygments for pretty printing if available
try:
    import pygments
    import pygments.lexers
    import pygments.formatters
except ImportError:
    pygments = None

from opsbro.log import cprint, logger
from opsbro.unixclient import get_json, get_local, request_errors
from opsbro.cli import get_opsbro_json, get_opsbro_local, print_info_title, print_2tab


def do_detect_list():
    try:
        (code, r) = get_opsbro_local('/agent/detectors')
    except request_errors, exp:
        logger.error(exp)
        return

    try:
        d = json.loads(r)
    except ValueError, exp:  # bad json
        logger.error('Bad return from the server %s' % exp)
        return

    e = []
    for i in d:
        e.append((i['name'], ','.join(i['tags'])))

    # Normal agent information
    print_info_title('Detectors')
    print_2tab(e)


def do_detect_run():
    try:
        (code, r) = get_opsbro_local('/agent/detectors/run')
    except request_errors, exp:
        logger.error(exp)
        return

    try:
        d = json.loads(r)
    except ValueError, exp:  # bad json
        logger.error('Bad return from the server %s' % exp)
        return

    print_info_title('Detectors results')
    all_tags = []
    new_tags = []
    for (k, v) in d.iteritems():
        all_tags.extend(v['tags'])
        new_tags.extend(v['new_tags'])
    e = [('Tags', ','.join(all_tags))]
    e.append(('New tags', {'value': ','.join(new_tags), 'color': 'green'}))
    print_2tab(e)


exports = {
    do_detect_list: {
        'keywords'   : ['detectors', 'list'],
        'args'       : [
        ],
        'description': 'Show detectors list'
    },

    do_detect_run : {
        'keywords'   : ['detectors', 'run'],
        'args'       : [
        ],
        'description': 'Run detectors'
    },
}
