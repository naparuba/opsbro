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
}
