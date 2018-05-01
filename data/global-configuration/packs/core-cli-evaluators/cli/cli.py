#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

import sys
import json
import base64
import time

from opsbro.characters import CHARACTERS
from opsbro.log import cprint, logger
from opsbro.unixclient import get_request_errors
from opsbro.cli import get_opsbro_local, print_info_title, post_opsbro_json, AnyAgent, print_h1


def do_evaluator_list(details=False):
    # We need an agent for this
    with AnyAgent():
        try:
            (code, r) = get_opsbro_local('/agent/evaluator/list')
        except get_request_errors() as exp:
            logger.error(exp)
            return
        
        try:
            d = json.loads(r)
        except ValueError as exp:  # bad json
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
            r = post_opsbro_json('/agent/evaluator/eval', {'expr': expr_64}, timeout=30)
        except get_request_errors() as exp:
            logger.error(exp)
            return
        
        print_info_title('Result')
        print r


def do_evaluator_wait_eval_true(expr, timeout=30):
    import itertools
    spinners = itertools.cycle(CHARACTERS.spinners)
    
    # We need an agent for this
    with AnyAgent():
        for i in xrange(timeout):
            expr_64 = base64.b64encode(expr)
            try:
                r = post_opsbro_json('/agent/evaluator/eval', {'expr': expr_64}, timeout=20)
            except get_request_errors() as exp:
                logger.error(exp)
                return
            
            if r is True:
                cprint('\n %s ' % CHARACTERS.arrow_left, color='grey', end='')
                cprint('%s ' % CHARACTERS.check, color='green', end='')
                cprint('The expression ', end='')
                cprint('%s' % expr, color='magenta', end='')
                cprint(' is now evaluated to ', end='')
                cprint('True', color='green')
                sys.exit(0)
            # Not detected? increase loop
            cprint('\r %s ' % spinners.next(), color='blue', end='')
            cprint('%s' % expr, color='magenta', end='')
            cprint(' is ', end='')
            cprint('not True', color='magenta', end='')
            cprint(' (%d/%d)' % (i, timeout), end='')
            # As we did not \n, we must flush stdout to print it
            sys.stdout.flush()
            time.sleep(1)
        cprint("\nThe expression %s was not evaluated to True after %s seconds" % (expr, timeout))
        sys.exit(2)


exports = {
    do_evaluator_list          : {
        'keywords'   : ['evaluator', 'list'],
        'args'       : [
            {'name': '--details', 'type': 'bool', 'default': False, 'description': 'Also print the details & documentation of the functions'},
        ],
        'description': 'List evaluator functions'
    },
    do_evaluator_eval          : {
        'keywords'   : ['evaluator', 'eval'],
        'args'       : [
        ],
        'description': 'Evaluate an expression'
    },
    
    do_evaluator_wait_eval_true: {
        'keywords'   : ['evaluator', 'wait-eval-true'],
        'args'       : [
            {'name': 'expr', 'description': 'Expression to evaluate'},
            {'name': '--timeout', 'type': 'int', 'default': 30, 'description': 'Timeout to let for the expression to be True'},
        ],
        'description': 'Wait until the expression is returned True'
    },
}
