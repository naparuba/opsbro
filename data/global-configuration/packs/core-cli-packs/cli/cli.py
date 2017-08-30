# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

import sys
import shutil
import os
import time
import datetime

# try pygments for pretty printing if available
try:
    import pygments
    import pygments.lexers
    import pygments.formatters
except ImportError:
    pygments = None

from opsbro.log import cprint, sprintf, logger
from opsbro.configurationmanager import configmgr
from opsbro.yamlmgr import yamler
from opsbro.cli import print_h1


def __print_pack_breadcumb(pack_name, pack_level, end='\n'):
    cprint('%-6s' % pack_level, color='blue', end='')
    cprint(' > ', end='')
    cprint('%-15s' % pack_name, color='yellow', end=end)


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
        cprint(' => ', color='grey', end='')
        is_valid = parameter_snap['is_valid']
        is_missing = parameter_snap['is_missing']
        is_default = parameter_snap['is_default']
        have_default = parameter_snap['have_default']
        default_value = parameter_snap['default_value']
        value = parameter_snap['value']
        # Maybe it is missing but a default value is setting it
        if is_missing:
            # Maybe not...
            if not have_default:
                cprint('[MISSING and no default]', color='red')
            else:
                cprint('%-10s (missing in parameters, so using the default value)' % default_value, color='grey')
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


def __split_pack_full_id(pack_full_id):
    if pack_full_id.count('.') != 1:
        logger.error('The pack_full_id %s parameter is malformed. Should be LEVEL.pack_name' % pack_full_id)
        sys.exit(2)
    pack_level, pack_name = pack_full_id.split('.')
    return pack_level, pack_name


# local.nagios.enable => (local, nagios, enable)
def __split_parameter_full_path(parameter_full_path):
    if parameter_full_path.count('.') < 2:
        logger.error('The parameter full path %s is malformed. Should be LEVEL.pack_name.parameter_name' % parameter_full_path)
        sys.exit(2)
    pack_level, pack_name, parameter_name = parameter_full_path.split('.', 2)
    return pack_level, pack_name, parameter_name


def __get_pack_directory(pack_level, pack_name):
    from opsbro.configurationmanager import configmgr
    data_dir = configmgr.data_dir
    pdir = os.path.join(data_dir, '%s-configuration' % pack_level, 'packs', pack_name)
    return pdir


def do_packs_show():
    logger.setLevel('ERROR')
    # We should already have load the configuration, so just dump it
    # now we read them, set it in our object
    parameters_from_local_configuration = configmgr.get_parameters_for_cluster_from_configuration()
    # print "Local parameters", parameters_from_local_configuration
    print_h1('Local agent parameters')
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
    
    print_h1('Packs')
    
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
            __print_pack_breadcumb(pack_name, level)
            
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
                __print_element_breadcumb(pack_name, pack_level, 'checks')
                cprint(' (%d)' % len(checks), color='magenta')
                for cname, check in checks.iteritems():
                    cprint('    - [', end='')
                    cprint('check.%-15s' % cname, color='cyan', end='')
                    cprint('] apply_on=%s' % (check['apply_on']))
            
            # Module
            module = pack_entry['module']
            if module is None:
                no_such_objects.append('module')
            else:
                __print_element_breadcumb(pack_name, pack_level, 'module')
                cprint(' : configuration=', end='')
                __print_element_parameters(module, pack_name, pack_level, 'parameters')
            
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
                    cprint('] configuration=', end='')
                    __print_element_parameters(collector, pack_name, pack_level, 'parameters')
            
            # handlers
            handlers = pack_entry['handlers']
            if len(handlers) == 0:
                no_such_objects.append('handlers')
            else:
                __print_element_breadcumb(pack_name, pack_level, 'handlers')
                cprint(' (%d)' % len(handlers), color='magenta')
                for hname, handler in handlers.iteritems():
                    cprint('    - [', end='')
                    cprint('handler.%-15s' % hname, color='cyan', end='')
                    cprint('] type=%s  severities=%s' % (handler['type'], ','.join(handler['severities'])))
            
            # generators
            generators = pack_entry['generators']
            if len(generators) == 0:
                no_such_objects.append('generators')
            else:
                __print_element_breadcumb(pack_name, pack_level, 'generators')
                cprint(' (%d)' % len(generators), color='magenta')
                for gname, generator in generators.iteritems():
                    cprint('    - [', end='')
                    cprint('generator.%-15s' % gname, color='cyan', end='')
                    cprint('] apply_on=%s' % (generator['apply_on']))
            
            # installors
            installors = pack_entry['installors']
            if len(installors) == 0:
                no_such_objects.append('installors')
            else:
                __print_element_breadcumb(pack_name, pack_level, 'installors')
                cprint(' (%d)' % len(installors), color='magenta')
                for iname, installor in installors.iteritems():
                    cprint('    - [', end='')
                    cprint('installor.%-15s' % iname, color='cyan', end='')
                    cprint(']')
            
            # Display what the pack do not manage (for info)
            if no_such_objects:
                cprint('  * The pack do not provide such objects: %s' % ','.join(no_such_objects), color='grey')
            print ''


def do_packs_list():
    from opsbro.packer import packer
    packs = packer.get_packs()
    all_pack_names = set()
    for (level, packs_in_level) in packs.iteritems():
        for (pname, _) in packs_in_level.iteritems():
            all_pack_names.add(pname)
    
    print_h1('Packs')
    
    pnames = list(all_pack_names)
    pnames.sort()
    for pname in pnames:
        present_before = False
        keywords = []  # useless but make lint code check happy
        cprint(' * ', end='')
        for level in ('global', 'zone', 'local'):
            if pname in packs[level]:
                (pack, _) = packs[level][pname]
                if present_before:
                    cprint('(overloaded by =>) ', color='green', end='')
                __print_pack_breadcumb(pname, level, end='')
                keywords = pack['keywords']
            present_before = True
        cprint('[keywords: %s]' % (','.join(keywords)), color='magenta')


def do_overload(pack_full_id, to_level='local'):
    from opsbro.packer import packer
    packs = packer.get_packs()
    pack_level, pack_name = __split_pack_full_id(pack_full_id)
    
    if pack_level not in ['global', 'zone']:
        logger.error('The pack level %s is not valid for the pack overload.' % pack_level)
        sys.exit(2)
    packs_from_level = packs[pack_level]
    if pack_name not in packs_from_level:
        logger.error('The pack %s is not known in the pack level %s' % (pack_name, pack_level))
        sys.exit(2)
    package_data, dir_name = packs[pack_level][pack_name]
    
    if to_level not in ['zone', 'local']:
        logger.error('The destination pack level %s is not valid for the pack overload.' % to_level)
        sys.exit(2)
    
    dest_dir = __get_pack_directory(to_level, pack_name)
    
    if os.path.exists(dest_dir):
        logger.error('The pack destination directory %s is already exiting. Please delete it first.' % dest_dir)
        sys.exit(2)
    # Ok now really copy it
    try:
        shutil.copytree(dir_name, dest_dir)
    except Exception, exp:
        logger.error('The pack overload did fail (from %s to %s) : %s' % (dir_name, dest_dir, exp))
        sys.exit(2)
    cprint(u'SUCCESS: ', color='green', end='')
    cprint('Pack ', end='')
    cprint('%s (%s)' % (pack_name, dir_name), color='green', end='')
    cprint(' is now overload at level ', end='')
    cprint(' %s (%s)' % (pack_level, dest_dir), color='magenta')


ENDING_SUFFIX = '#___ENDING___'


def do_parameters_set(parameter_full_path, value):
    pack_level, pack_name, parameter_name = __split_parameter_full_path(parameter_full_path)
    pack_root_dir = __get_pack_directory(pack_level, pack_name)
    parameters_file_path = os.path.join(pack_root_dir, 'parameters', 'parameters.yml')
    o = __get_object_from_parameter_file(parameters_file_path, suffix=ENDING_SUFFIX)
    
    try:
        python_value = yamler.loads('%s' % value)
    except Exception, exp:
        logger.error('Cannot load the value %s as a valid parameter: %s' % (value, exp))
        sys.exit(2)
    
    # Get the value as from yaml
    o[parameter_name] = python_value
    
    # Add a change history entry
    # BEWARE: only a oneliner!
    value_str = value.replace('\n', ' ')
    change_line = '# CHANGE: (%s) SET %s => %s' % (datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S'), parameter_name, value_str)
    yamler.add_document_ending_comment(o, change_line, ENDING_SUFFIX)
    
    result_str = yamler.dumps(o)
    tmp_file = '%s.tmp' % parameters_file_path
    f = open(tmp_file, 'w')
    f.write(result_str)
    f.close()
    shutil.move(tmp_file, parameters_file_path)
    
    cprint('OK: ', color='green', end='')
    cprint('%s (%s)' % (parameter_full_path, parameters_file_path), color='magenta', end='')
    cprint(' SET ', end='')
    cprint(parameter_name, color='magenta', end='')
    cprint(' => ', end='')
    cprint(value, color='green')


def __get_object_from_parameter_file(parameters_file_path, suffix=''):
    if not os.path.exists(parameters_file_path):
        logger.error('The parameters file %s is missing' % parameters_file_path)
        sys.exit(2)
    with open(parameters_file_path, 'r') as f:
        buf = f.read()
    # If we want to suffix the file, be sure to only add a line
    # and beware of the void file too
    if suffix:
        if buf:
            if buf.endswith('\n'):
                buf += '%s\n' % suffix
            else:
                buf += '\n%s\n' % suffix
        else:  # void file
            buf = '%s\n' % suffix
    
    # As we have a parameter style, need to insert dummy key entry to have all comments, even the first key one
    o = yamler.loads(buf, force_document_comment_to_first_entry=True)
    return o


def do_parameters_get(parameter_full_path):
    pack_level, pack_name, parameter_name = __split_parameter_full_path(parameter_full_path)
    pack_root_dir = __get_pack_directory(pack_level, pack_name)
    parameters_file_path = os.path.join(pack_root_dir, 'parameters', 'parameters.yml')
    o = __get_object_from_parameter_file(parameters_file_path)
    if parameter_name not in o:
        logger.error('Cannot find the parameter %s in the parameters file %s' % (parameter_name, parameters_file_path))
        sys.exit(2)
    
    # yaml is putting us a ugly '...' as last line, remove it
    lines = yamler.dumps(o[parameter_name]).splitlines()
    if '...' in lines:
        lines.remove('...')
    
    value_string = '\n'.join(lines)
    cprint('%s' % parameter_full_path, color='magenta', end='')
    cprint(' => ', end='')
    cprint(value_string, color='green')
    
    # Now if there are, get the comments
    comment = yamler.get_key_comment(o, parameter_name)
    if comment is not None:
        lines = comment.splitlines()
        for line in lines:
            cprint('  | %s' % line, color='grey')


exports = {
    
    do_packs_show    : {
        'keywords'   : ['packs', 'show'],
        'args'       : [],
        'description': 'Print pack informations & contents'
    },
    
    do_packs_list    : {
        'keywords'   : ['packs', 'list'],
        'args'       : [],
        'description': 'List packs'
    },
    
    do_overload      : {
        'keywords'   : ['packs', 'overload'],
        'args'       : [
            {'name': 'pack_full_id', 'description': 'Pack full id (of the form LEVEL.pack_name, for example global.dns) that will be overload to a lower level'},
            {'name': '--to-level', 'default': 'local', 'description': 'Level to overload the pack, local or zone, default to local.'},
        ],
        'description': 'Overload (copy in a more priotiry pack level) a pack. For example copy a pack from the global level to the local one.'
    },
    
    do_parameters_set: {
        'keywords'   : ['packs', 'parameters', 'set'],
        'args'       : [
            {'name': 'parameter_full_path', 'description': 'Parameter path of the form LEVEL.packs.PACK_NAME.KEY'},
            {'name': 'value', 'description': 'Value to set for this parameter'},
        ],
        'description': 'List packs'
    },
    
    do_parameters_get: {
        'keywords'   : ['packs', 'parameters', 'get'],
        'args'       : [
            {'name': 'parameter_full_path', 'description': 'Parameter path of the form LEVEL.packs.PACK_NAME.KEY'},
        ],
        'description': 'List packs'
    },
    
}
