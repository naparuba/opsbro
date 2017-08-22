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

from opsbro.log import cprint, logger
from opsbro.configurationmanager import configmgr


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
    
    from opsbro.packer import packer
    packs = {'global': {}, 'zone': {}, 'local': {}}
    for level in packer.packs:
        for pname in packer.packs[level]:
            packs[level][pname] = {'checks': {}, 'module': None, 'collectors': {}, 'handlers': {}, 'generators': {}, 'installors': {}}
    
    from opsbro.monitoring import monitoringmgr
    checks = monitoringmgr.checks
    for cname, check in checks.iteritems():
        pack_name = check['pack_name']
        pack_level = check['pack_level']
        packs[pack_level][pack_name]['checks'][cname] = check
    
    from opsbro.modulemanager import modulemanager
    modules = modulemanager.modules
    for module in modules:
        pack_name = module.pack_name
        pack_level = module.pack_level
        packs[pack_level][pack_name]['module'] = module
    
    from opsbro.collectormanager import collectormgr
    collectors = collectormgr.collectors
    for colname, collector in collectors.iteritems():
        print collector
        pack_name = collector['inst'].pack_name
        pack_level = collector['inst'].pack_level
        packs[pack_level][pack_name]['collectors'][colname] = collector

    
    from opsbro.handlermgr import handlermgr
    handlers = handlermgr.handlers
    for hname, handler in handlers.iteritems():
        pack_name = handler['pack_name']
        pack_level = handler['pack_level']
        packs[pack_level][pack_name]['handlers'][hname] = handler
    
    from opsbro.generatormgr import generatormgr
    generators = generatormgr.generators
    for gname, generator in generators.iteritems():
        pack_name = generator['pack_name']
        pack_level = generator['pack_level']
        packs[pack_level][pack_name]['generators'][gname] = generator
    
    from opsbro.installermanager import installormgr
    installors = installormgr.install_rules
    for installator in installors:
        iname = installator.name
        pack_name = installator.pack_name
        pack_level = installator.pack_level
        packs[pack_level][pack_name]['installors'][iname] = installator

    print "Finally:"
    from pprint import pprint
    pprint(packs)
    
    for level in ('global', 'zone', 'local'):
        cprint('[ Packs Level %s ]' % level, color='blue')
        pack_names = packs[level].keys()
        pack_names.sort()
        if len(pack_names) == 0:
            cprint('  No packs are available', color='grey')
            continue
        for pack_name in pack_names:
            pack_entry = packs[level][pack_name]
            cprint('  * Pack %s:' % pack_name, color='magenta')
            # * checks
            # * module
            # * collectors
            # * handlers
            # * generators
            # * installors
            checks = pack_entry['checks']
            if len(checks) == 0:
                cprint('   * Checks: No checks available', color='grey')
            else:
                cprint('   * Checks (%d):' % len(checks), color='magenta')
                for cname, check in checks.iteritems():
                    cprint('    - %s (apply on:%s)' % (cname, check['apply_on']))

            # Module
            module = pack_entry['module']
            if module is None:
                cprint('   * Module: No available', color='grey')
            else:
                cprint('   * Module: %s' % module.__class__.__name__.lower(), color='magenta')

            # collectors
            collectors = pack_entry['collectors']
            if len(collectors) == 0:
                cprint('   * Collectors: No collectors available', color='grey')
            else:
                cprint('   * Collectors (%d):' % len(collectors), color='magenta')
                for colname, collector in collectors.iteritems():
                    cprint('    - %s ' % (colname))

            # handlers
            handlers = pack_entry['handlers']
            if len(handlers) == 0:
                cprint('   * Handlers: No handlers available', color='grey')
            else:
                cprint('   * Handlers (%d):' % len(handlers), color='magenta')
                for hname, handler in handlers.iteritems():
                    cprint('    - %s   type=%s  severities=%s' % (hname, handler['type'], ','.join(handler['severities'])))

            # generators
            generators = pack_entry['generators']
            if len(generators) == 0:
                cprint('   * Generators: No generators available', color='grey')
            else:
                cprint('   * Generators (%d):' % len(generators), color='magenta')
                for gname, generator in generators.iteritems():
                    cprint('    - %s (apply_on %s)' % (gname, generator['apply_on']))

            # installors
            installors = pack_entry['installors']
            if len(installors) == 0:
                cprint('   * Installors: No installors available', color='grey')
            else:
                cprint('   * Installors (%d):' % len(installors), color='magenta')
                for iname, installor in installors.iteritems():
                    cprint('    - %s ' % iname)


exports = {
    
    do_configuration_print: {
        'keywords'   : ['config', 'show'],
        'args'       : [],
        'description': 'Print configuration'
    },
    
}
