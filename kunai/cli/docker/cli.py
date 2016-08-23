#!/usr/bin/env python

# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com


# try pygments for pretty printing if available
try:
    import pygments
    import pygments.lexers
    import pygments.formatters
except ImportError:
    pygments = None

from kunai.log import cprint, logger
from kunai.cli import get_kunai_json, get_kunai_local, print_info_title, print_2tab


def do_docker_show():
    d = get_kunai_json('/docker/stats')
    scontainers = d.get('containers')
    simages = d.get('images')

    print_info_title('Docker Stats')
    if not scontainers:
        cprint("No running containers", color='grey')
    for (cid, stats) in scontainers.iteritems():
        print_info_title('Container:%s' % cid)
        keys = stats.keys()
        keys.sort()
        e = []
        for k in keys:
            sd = stats[k]
            e.append((k, sd['value']))

        # Normal agent information
        print_2tab(e, capitalize=False, col_size=30)

    for (cid, stats) in simages.iteritems():
        print_info_title('Image:%s (sum)' % cid)
        keys = stats.keys()
        keys.sort()
        e = []
        for k in keys:
            sd = stats[k]
            e.append((k, sd['value']))

        # Normal agent information
        print_2tab(e, capitalize=False, col_size=30)


exports = {

    do_docker_show: {
        'keywords'   : ['docker', 'show'],
        'args'       : [],
        'description': 'Show stats from docker containers and images'
    },

}
