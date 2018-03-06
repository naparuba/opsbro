#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com


import json
import base64

from opsbro.log import cprint, logger
from opsbro.unixclient import get_request_errors
from opsbro.cli import get_opsbro_local, print_info_title, post_opsbro_json, wait_for_agent_started, AnyAgent, print_h1


def do_evaluator_list(details=False):
    # We need an agent for this
    with AnyAgent():
        try:
            (code, r) = get_opsbro_local('/agent/evaluator/list')
        except get_request_errors(), exp:
            logger.error(exp)
            return
        
        try:
            d = json.loads(r)
        except ValueError, exp:  # bad json
            logger.error('Bad return from the server %s' % exp)
            return
        
        # Group by
        groups = {}
        for f in d:
            fname = f['name']
            gname = f['group']
            if gname not in groups:
                groups[gname] = {}
            groups[gname][fname] = f
        
        gnames = groups.keys()
        gnames.sort()
        
        for gname in gnames:
            print_h1(gname)
            group_functions = groups[gname]
            fnames = group_functions.keys()
            fnames.sort()
            
            for fname in fnames:
                f = group_functions[fname]
                prototype = f['prototype']
                doc = f['doc']
                
                cprint(fname, color='green', end='')
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
                if details:
                    cprint(doc, color='grey')


def do_evaluator_eval(expr):
    # We need an agent for this
    with AnyAgent():
        expr_64 = base64.b64encode(expr)
        try:
            r = post_opsbro_json('/agent/evaluator/eval', {'expr': expr_64})
        except get_request_errors(), exp:
            logger.error(exp)
            return
        
        print_info_title('Result')
        print r


exports = {
    do_evaluator_list: {
        'keywords'   : ['evaluator', 'list'],
        'args'       : [
            {'name': '--details', 'type': 'bool', 'default': False, 'description': 'Also print the details & documentation of the functions'},
        ],
        'description': 'List evaluator functions'
    },
    do_evaluator_eval: {
        'keywords'   : ['evaluator', 'eval'],
        'args'       : [
        ],
        'description': 'Evaluate an expression'
    },
    
}
