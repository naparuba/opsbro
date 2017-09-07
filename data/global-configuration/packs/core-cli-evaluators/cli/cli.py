#!/usr/bin/env python

# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com


import json
import base64

from opsbro.log import cprint, logger
from opsbro.unixclient import request_errors
from opsbro.cli import get_opsbro_local, print_info_title, post_opsbro_json


def do_evaluator_list():
    try:
        (code, r) = get_opsbro_local('/agent/evaluator/list')
    except request_errors, exp:
        logger.error(exp)
        return
    
    try:
        d = json.loads(r)
    except ValueError, exp:  # bad json
        logger.error('Bad return from the server %s' % exp)
        return
    
    print_info_title('Functions')
    for f in d:
        cprint('*' * 80, color='magenta')
        name = f['name']
        prototype = f['prototype']
        doc = f['doc']
        cprint(name, color='magenta', end='')
        cprint('(', end='')
        if prototype:
            _s_args = []
            for arg in prototype:
                kname = arg[0]
                def_value = arg[1]
                if def_value != '__NO_DEFAULT__':
                    _s_args.append('%s=%s' % (kname, def_value))
                else:
                    _s_args.append('%s' % kname)
            cprint(', '.join(_s_args), color='yellow', end='')
        cprint(')')
        cprint("Documentation:", color='green')
        print doc
        print ''


def do_evaluator_eval(expr):
    print expr
    expr_64 = base64.b64encode(expr)
    try:
        r = post_opsbro_json('/agent/evaluator/eval', {'expr': expr_64})
    except request_errors, exp:
        logger.error(exp)
        return
    
    print_info_title('Result')
    print r


exports = {
    do_evaluator_list: {
        'keywords'   : ['evaluator', 'list'],
        'args'       : [
        ],
        'description': 'List evaluator functions'
    },
    do_evaluator_eval: {
        'keywords'   : ['evaluator', 'eval'],
        'args'       : [
            # {'name' : '--expression', 'description':'Expression to eval'},
        ],
        'description': 'Evaluate an expression'
    },
    
}
