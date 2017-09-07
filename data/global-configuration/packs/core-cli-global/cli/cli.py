#!/usr/bin/env python

# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com


from opsbro.log import cprint
from opsbro.info import VERSION


def do_version():
    cprint(VERSION)


exports = {
    do_version: {
        'keywords'   : ['version'],
        'args'       : [],
        'description': 'Print the daemon version'
    },
}
