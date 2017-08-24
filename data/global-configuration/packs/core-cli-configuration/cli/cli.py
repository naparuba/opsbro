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


def __print_element_breadcumb(pack_name, pack_level, what):
    cprint('  * ', end='')
    cprint(pack_level, color='blue', end='')
    cprint(' > ', end='')
    cprint(pack_name, color='yellow', end='')
    cprint(' > ', end='')
    cprint(what, color='cyan', end='')


def __print_element_parameters(elt, pack_name, pack_level, what):
    config_snapshot = elt.get_configuration_snapshot()
    if config_snapshot['state'] == 'OK':
        cprint('OK', color='green')
    else:
        cprint('%s  => %s' % (config_snapshot['state'], config_snapshot['errors']), color='red')
    for parameter_name, parameter_snap in config_snapshot['parameters'].iteritems():
        cprint('    - ', end='')
        cprint('%s.packs.%s.%s.' % (pack_level, pack_name, what), color='grey', end='')
        cprint('%-15s' % parameter_name, color='magenta', end='')
        cprint(' => ', end='')
        is_valid = parameter_snap['is_valid']
        is_missing = parameter_snap['is_missing']
        is_default = parameter_snap['is_default']
        have_default = parameter_snap['have_default']
        default_value = parameter_snap['default_value']
        value = parameter_snap['value']
        if is_missing:
            cprint('[MISSING]', color='red')
        else:
            if not is_valid:
                cprint('[INVALID] ', color='red', end='')
            if not is_default:
                cprint('%-10s' % value, color='green', end='')
                if have_default:
                    cprint(' (default=%s)' % default_value, color='grey')
                else:
                    cprint('(no default)', color='grey')
            else:
                cprint('%-10s' % value, end='')
                cprint(' (is default)', color='grey')


def do_configuration_print():
    logger.setLevel('ERROR')
    # We should already have load the configuration, so just dump it
    # now we read them, set it in our object
    parameters_from_local_configuration = configmgr.get_parameters_for_cluster_from_configuration()
    # print "Local parameters", parameters_from_local_configuration
    print '*' * 40
    print '         Local agent parameter'
    print '*' * 40
    key_names = parameters_from_local_configuration.keys()
    key_names.sort()
    for k in key_names:
        v = parameters_from_local_configuration[k]
        cprint('  * ', end='')
        cprint('%-15s' % k, color='magenta', end='')
        cprint(' => ', end='')
        cprint('%s\n' % v, color='green', end='')
    
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
    
    print '*' * 40
    print '         Packs'
    print '*' * 40
    
    for level in ('global', 'zone', 'local'):
        cprint('========== Level ', end='')
        cprint(level, color='blue')
        pack_names = packs[level].keys()
        pack_names.sort()
        if len(pack_names) == 0:
            cprint('  No packs are available', color='grey')
            continue
        for pack_name in pack_names:
            pack_entry = packs[level][pack_name]
            cprint('==== Pack ', end='')
            cprint(level, color='blue', end='')
            cprint(' > ', end='')
            cprint('%s' % pack_name, color='yellow')
            
            #### Now loop over objects
            # * checks
            # * module
            # * collectors
            # * handlers
            # * generators
            # * installors
            no_such_objects = []
            checks = pack_entry['checks']
            if len(checks) == 0:
                no_such_objects.append('checks')
            else:
                cprint('   * Checks (%d):' % len(checks), color='magenta')
                for cname, check in checks.iteritems():
                    cprint('    - %s (apply on:%s)' % (cname, check['apply_on']))
            
            # Module
            module = pack_entry['module']
            if module is None:
                no_such_objects.append('module')
            else:
                __print_element_breadcumb(pack_name, pack_level, 'module')
                cprint(' : configuration=', end='')
                __print_element_parameters(module, pack_name, pack_level, 'module')
            
            # collectors
            collectors = pack_entry['collectors']
            if len(collectors) == 0:
                no_such_objects.append('collectors')
            else:
                __print_element_breadcumb(pack_name, pack_level, 'collectors')
                cprint(' (%d)' % len(collectors), color='magenta')
                for colname, collector_d in collectors.iteritems():
                    collector = collector_d['inst']
                    cprint('    - [', end='')
                    cprint('collectors.%-15s' % colname, end='', color='cyan')
                    cprint('] configuration=' , end='')
                    __print_element_parameters(collector, pack_name, pack_level, 'parameters')
            
            # handlers
            handlers = pack_entry['handlers']
            if len(handlers) == 0:
                no_such_objects.append('handlers')
            else:
                cprint('   * Handlers (%d):' % len(handlers), color='magenta')
                for hname, handler in handlers.iteritems():
                    cprint('    - %s   type=%s  severities=%s' % (hname, handler['type'], ','.join(handler['severities'])))
            
            # generators
            generators = pack_entry['generators']
            if len(generators) == 0:
                no_such_objects.append('generators')
            else:
                cprint('   * Generators (%d):' % len(generators), color='magenta')
                for gname, generator in generators.iteritems():
                    cprint('    - %s (apply_on %s)' % (gname, generator['apply_on']))
            
            # installors
            installors = pack_entry['installors']
            if len(installors) == 0:
                no_such_objects.append('installors')
            else:
                cprint('   * Installors (%d):' % len(installors), color='magenta')
                for iname, installor in installors.iteritems():
                    cprint('    - %s ' % iname)
            
            # Display what the pack do not manage (for info)
            if no_such_objects:
                cprint('  * The pack do not provide such objects: %s' % ','.join(no_such_objects), color='grey')
            print ''


exports = {
    
    do_configuration_print: {
        'keywords'   : ['config', 'show'],
        'args'       : [],
        'description': 'Print configuration'
    },
    
}
