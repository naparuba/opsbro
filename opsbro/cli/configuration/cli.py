#!/usr/bin/env python

# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

import os

# try pygments for pretty printing if available
try:
    import pygments
    import pygments.lexers
    import pygments.formatters
except ImportError:
    pygments = None

from opsbro.log import cprint, logger
from opsbro.configurationmanager import configmgr
from opsbro.defaultpaths import DEFAULT_LIBEXEC_DIR, DEFAULT_LOCK_PATH, DEFAULT_DATA_DIR, DEFAULT_LOG_DIR
from opsbro.cli import get_opsbro_json, get_opsbro_local, print_info_title, print_2tab


def do_configuration_print():
    logger.setLevel('ERROR')
    # We should already have load the configuration, so just dump it
    # now we read them, set it in our object
    parameters_from_local_configuration = configmgr.get_parameters_for_cluster_from_configuration()
    # print "Local parameters", parameters_from_local_configuration
    print "Local agent parameter:"
    key_names = parameters_from_local_configuration.keys()
    key_names.sort()
    for k in key_names:
        v = parameters_from_local_configuration[k]
        cprint('  * ', end='')
        cprint('%-15s' % k, color='magenta', end='')
        cprint(' => ', end='')
        cprint('%s\n' % v, color='green', end='')
    
    # print configmgr.declared_parameters
    print "Politics:"
    _types = ['collector', 'module']
    for t in _types:
        print " * %ss" % t.capitalize()
        keys = configmgr.declared_parameters[t].keys()
        keys.sort()
        for k in keys:
            obj_parameters = configmgr.declared_parameters[t][k]
            print "    - %-15s" % k
            for (param_name, param_desc) in obj_parameters.iteritems():
                print "       - %-15s => %s" % (param_name, param_desc)


exports = {
    
    do_configuration_print: {
        'keywords'   : ['config', 'show'],
        'args'       : [],
        'description': 'Print configuration'
    },
    
}
