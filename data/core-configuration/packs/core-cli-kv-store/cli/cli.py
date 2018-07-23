#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

from __future__ import print_function
import sys
import base64
import time

from opsbro.characters import CHARACTERS
from opsbro.log import cprint, logger
from opsbro.unixclient import get_request_errors
from opsbro.cli import print_info_title, post_opsbro_json, get_opsbro_local, put_opsbro_json, delete_opsbro_json
from opsbro.util import bytes_to_unicode


def do_kv_store_get(key_name):
    try:
        (code, value) = get_opsbro_local('/kv/%s' % key_name)
    except get_request_errors() as exp:
        logger.error('Cannot join opsbro agent for info: %s' % exp)
        sys.exit(1)
    if code == 404:
        cprint('ERROR: the key %s does not exist' % key_name, color='red')
        sys.exit(2)
    value = bytes_to_unicode(value)
    cprint("%s::%s" % (key_name, value))


def do_kv_store_delete(key_name):
    if not key_name:
        cprint("Need a key-name parameter", color='red')
        sys.exit(2)
    
    cprint(' - Deleting key ', end='')
    cprint(key_name, color='magenta', end='')
    cprint(' : ', end='')
    sys.stdout.flush()
    try:
        delete_opsbro_json('/kv/%s' % key_name)
    except get_request_errors() as exp:
        cprint(CHARACTERS.cross, color='red')
        logger.error(exp)
        sys.exit(2)
    cprint(CHARACTERS.check, color='green')


def do_kv_store_put(key_name, value):
    if not key_name:
        cprint("Need a key-name parameter", color='red')
        sys.exit(2)
    
    cprint(' - Set key ', end='')
    cprint(key_name, color='magenta', end='')
    cprint(' : ', end='')
    sys.stdout.flush()
    try:
        put_opsbro_json('/kv/%s' % key_name, value)
    except get_request_errors() as exp:
        cprint(CHARACTERS.cross, color='red')
        logger.error(exp)
        sys.exit(2)
    cprint(CHARACTERS.check, color='green')


def do_kv_store_list():
    expr_64 = base64.b64encode(expr)
    try:
        r = post_opsbro_json('/agent/evaluator/eval', {'expr': expr_64}, timeout=30)
    except get_request_errors() as exp:
        logger.error(exp)
        return
    
    print_info_title('Result')
    cprint(r)


def do_kv_store_wait_value(key_name, expected_value, timeout=30):
    import itertools
    spinners = itertools.cycle(CHARACTERS.spinners)
    
    for i in range(timeout):
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
        cprint('\r %s ' % next(spinners), color='blue', end='')
        cprint('%s' % expr, color='magenta', end='')
        cprint(' is ', end='')
        cprint('not True', color='magenta', end='')
        cprint(' (%d/%d)' % (i, timeout), end='')
        # As we did not \n, we must flush stdout to print it
        sys.stdout.flush()
        time.sleep(1)
    cprint("\nThe expression %s was not evaluated to True after %s seconds" % (expr, timeout))
    sys.exit(2)


def do_kv_store_wait_exists(key_name, timeout=30):
    import itertools
    spinners = itertools.cycle(CHARACTERS.spinners)
    
    for i in range(timeout):
        try:
            (code, value) = get_opsbro_local('/kv/%s' % key_name)
        except get_request_errors() as exp:
            logger.error('Cannot join opsbro agent for info: %s' % exp)
            sys.exit(1)
        
        if code == 200:
            cprint('\n %s ' % CHARACTERS.arrow_left, color='grey', end='')
            cprint('%s ' % CHARACTERS.check, color='green', end='')
            cprint('The key ', end='')
            cprint('%s' % key_name, color='magenta', end='')
            cprint(' does ', end='')
            cprint('Exists', color='green')
            sys.exit(0)
        # Not detected? increase loop
        cprint('\r %s ' % next(spinners), color='blue', end='')
        cprint('%s' % key_name, color='magenta', end='')
        cprint(' is ', end='')
        cprint('not Existing', color='magenta', end='')
        cprint(' (%d/%d)' % (i, timeout), end='')
        # As we did not \n, we must flush stdout to print it
        sys.stdout.flush()
        time.sleep(1)
    cprint("\nThe key %s was not set after %s seconds" % (key_name, timeout))
    sys.exit(2)


exports = {
    do_kv_store_get        : {
        'keywords'             : ['kv-store', 'get'],
        'args'                 : [
            {'name': 'key-name', 'description': 'Name of the key to get'},
        ],
        'allow_temporary_agent': {'enabled': True, },
        'description'          : 'Get the value of a key'
    },
    
    do_kv_store_delete     : {
        'keywords'             : ['kv-store', 'delete'],
        'args'                 : [
            {'name': 'key-name', 'description': 'Name of the key to delete'},
        ],
        'allow_temporary_agent': {'enabled': True, },
        'description'          : 'Delete a key/value'
    },
    
    do_kv_store_put        : {
        'keywords'             : ['kv-store', 'put'],
        'args'                 : [
            {'name': 'key-name', 'description': 'Name of the key to put'},
            {'name': 'value', 'description': 'Value to set'},
        ],
        'allow_temporary_agent': {'enabled': True, },
        'description'          : 'Put a new value for a key',
    },
    
    #    do_kv_store_list       : {
    #        'keywords'   : ['kv-store', 'list'],
    #        'args'       : [
    #        ],
    # 'allow_temporary_agent': {'enabled': True, },
    #        'description': 'List the key stored in the agent'
    #    },
    
    #    do_kv_store_wait_value : {
    #        'keywords'   : ['kv-store', 'wait-value'],
    #        'args'       : [
    #            {'name': 'key-name', 'description': 'Name of the key to wait'},
    #            {'name': 'expected-value', 'description': 'Value to wait for'},
    #            {'name': '--timeout', 'type': 'int', 'default': 30, 'description': 'Timeout to let for the value to be the expected one'},
    #        ],
    # 'allow_temporary_agent': {'enabled': True, },
    #        'description': 'Wait until the key have the expected value'
    #    },
    
    do_kv_store_wait_exists: {
        'keywords'             : ['kv-store', 'wait-exists'],
        'args'                 : [
            {'name': 'key-name', 'description': 'Name of the key to wait for exists'},
            {'name': '--timeout', 'type': 'int', 'default': 30, 'description': 'Timeout to let for the key to exists'},
        ],
        'allow_temporary_agent': {'enabled': True, },
        'description'          : 'Wait until the key does exists'
    },
}
