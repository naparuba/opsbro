#!/usr/bin/env python

# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com


from opsbro.log import cprint, is_tty
from opsbro.info import VERSION, BANNER, TXT_BANNER


def do_version():
    cprint(VERSION)


def do_banner():
    if is_tty():
        cprint(BANNER)
    else:
        cprint(TXT_BANNER, color='blue')

def do_sponsor():
    from opsbro.authors import NINJA
    from opsbro.cli_display import print_h1
    
    print_h1('Our sponsor')
    cprint(NINJA)
    cprint('Shinken Solutions Team is working on a great monitoring solution: ', end='')
    cprint('Shinken Enterprise', color='magenta', end='')
    cprint(' (http://shinken-solutions.com).')
    cprint('Have a look if you need a powerful monitoring with:')
    cprint(' - unlimited scalability')
    cprint(' - high availability')
    cprint(' - advanced configuration with multi-role communication inside')
    cprint(' - powerful dashboards (/.__.)/ \(.__.\)')
    cprint('')


exports = {
    do_version: {
        'keywords'   : ['version'],
        'args'       : [],
        'description': 'Print the daemon version'
    },
    do_banner: {
        'keywords'   : ['banner'],
        'args'       : [],
        'description': 'Print the daemon banner'
    },
    do_sponsor: {
        'keywords'   : ['sponsor'],
        'args'       : [],
        'description': 'Show OpsBro sponsor (Shinken Solutions)'
    },
}
