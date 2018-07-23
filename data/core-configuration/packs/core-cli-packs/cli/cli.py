# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

import sys
import shutil
import os

from opsbro.characters import CHARACTERS
from opsbro.log import cprint, sprintf, logger
from opsbro.cli_display import print_h1, print_h2, print_h3, print_element_breadcumb, yml_parameter_get, yml_parameter_set
from opsbro.packer import packer
from opsbro.misc.lolcat import lolcat
from opsbro.topic import topiker, VERY_ALL_TOPICS, TOPICS_LABELS


def __print_pack_breadcumb(pack_name, pack_level, end='\n', topic_picto='large'):
    cprint(__get_pack_breadcumb(pack_name, pack_level, end=end, topic_picto=topic_picto), end='')


def __get_pack_breadcumb(pack_name, pack_level, end='', topic_picto='large'):
    pack_topics = packer.get_pack_all_topics(pack_name)
    pack_main_topic = 'generic'
    if len(pack_topics) != 0:
        pack_main_topic = pack_topics[0]
    topic_color = topiker.get_color_id_by_topic_string(pack_main_topic)
    if topic_picto == 'large':
        picto = u'%s%s ' % (CHARACTERS.corner_top_left, CHARACTERS.hbar * 2)
    else:
        picto = u'%s ' % CHARACTERS.topic_small_picto
    res = lolcat.get_line(picto, topic_color, spread=None) \
          + sprintf('%-6s' % pack_level, color='blue', end='') \
          + sprintf(' > ', end='') \
          + sprintf('%-15s' % pack_name, color='yellow', end='') \
          + end
    
    return res


def __print_element_parameters(elt, pack_name, pack_level, main_topic_color, what, offset):
    __print_line_header(main_topic_color)
    cprint('   %sParameters: ' % (' ' * offset), color='grey', end='')
    config_snapshot = elt.get_configuration_snapshot()
    if len(config_snapshot['parameters']) == 0:
        cprint('(none)', color='grey')
    elif config_snapshot['state'] == 'OK':
        cprint(CHARACTERS.check, color='green')
    else:
        cprint('%s  %s %s' % (config_snapshot['state'], CHARACTERS.arrow_left, config_snapshot['errors']), color='red')
    for parameter_name, parameter_snap in config_snapshot['parameters'].items():
        __print_line_header(main_topic_color)
        cprint('   %s- ' % (' ' * offset), end='')
        cprint('%s.packs.%s.%s.' % (pack_level, pack_name, what), color='grey', end='')
        cprint('%-15s' % parameter_name, color='magenta', end='')
        cprint(' %s ' % CHARACTERS.arrow_left, color='grey', end='')
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


def __print_line_header(main_topic_color):
    cprint(lolcat.get_line(CHARACTERS.vbar, main_topic_color, spread=None), end='')


def do_packs_show():
    logger.setLevel('ERROR')
    # We should already have load the configuration, so just dump it
    # now we read them, set it in our object
    
    from opsbro.packer import packer
    packs = {'core': {}, 'global': {}, 'zone': {}, 'local': {}}
    for level in packer.packs:
        for pname in packer.packs[level]:
            packs[level][pname] = {'checks': {}, 'module': None, 'collectors': {}, 'generators': {}}
    
    from opsbro.monitoring import monitoringmgr
    checks = monitoringmgr.checks
    for cname, check in checks.items():
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
    for colname, collector in collectors.items():
        pack_name = collector['inst'].pack_name
        pack_level = collector['inst'].pack_level
        packs[pack_level][pack_name]['collectors'][colname] = collector
    
    from opsbro.generatormgr import generatormgr
    generators = generatormgr.generators
    for gname, generator in generators.items():
        pack_name = generator.pack_name
        pack_level = generator.pack_level
        packs[pack_level][pack_name]['generators'][gname] = generator
    
    for level in ('core', 'global', 'zone', 'local'):
        s1 = sprintf('Packs at level ', color='yellow', end='')
        s2 = sprintf(level, color='blue', end='')
        print_h1(s1 + s2, raw_title=True)
        pack_names = list(packs[level].keys())
        pack_names.sort()
        if len(pack_names) == 0:
            cprint('  No packs are available at the level %s' % level, color='grey')
            continue
        for pack_name in pack_names:
            pack_entry = packs[level][pack_name]
            pack_breadcumb_s = __get_pack_breadcumb(pack_name, level)
            cprint(pack_breadcumb_s)
            
            main_topic, secondary_topics = packer.get_pack_main_and_secondary_topics(pack_name)
            main_topic_color = topiker.get_color_id_by_topic_string(main_topic)
            if main_topic != 'generic':
                
                __print_line_header(main_topic_color)
                cprint(u' * Main topic: ', color='grey', end='')
                s = lolcat.get_line(main_topic, main_topic_color, spread=None)
                cprint(s)
            if secondary_topics:
                _numeral = 's' if len(secondary_topics) > 1 else ''
                s = u' * Secondary topic%s: %s' % (_numeral, ', '.join(secondary_topics))
                __print_line_header(main_topic_color)
                cprint(s, color='grey')
            
            #### Now loop over objects
            # * checks
            # * module
            # * collectors
            # * handlers
            # * generators
            no_such_objects = []
            checks = pack_entry['checks']
            if len(checks) == 0:
                no_such_objects.append('checks')
            else:
                __print_line_header(main_topic_color)
                print_element_breadcumb(pack_name, pack_level, 'checks')
                cprint(' (%d)' % len(checks), color='magenta')
                for cname, check in checks.items():
                    __print_line_header(main_topic_color)
                    cprint('  - ', end='')
                    cprint('checks > %-15s' % cname.split(os.sep)[-1], color='cyan', end='')
                    cprint(' if_group=%s' % (check['if_group']))
            
            # Module
            module = pack_entry['module']
            if module is None:
                no_such_objects.append('module')
            else:
                __print_line_header(main_topic_color)
                print_element_breadcumb(pack_name, pack_level, 'module')
                # cprint(' : configuration=', end='')
                cprint('')
                offset = 0
                __print_element_parameters(module, pack_name, pack_level, main_topic_color, 'parameters', offset)
            
            # collectors
            collectors = pack_entry['collectors']
            if len(collectors) == 0:
                no_such_objects.append('collectors')
            else:
                __print_line_header(main_topic_color)
                print_element_breadcumb(pack_name, pack_level, 'collectors')
                cprint(' (%d)' % len(collectors), color='magenta')
                for colname, collector_d in collectors.items():
                    __print_line_header(main_topic_color)
                    collector = collector_d['inst']
                    cprint('  - ', end='')
                    cprint('collectors > %-15s' % colname, end='', color='cyan')
                    cprint('')
                    offset = 1
                    __print_element_parameters(collector, pack_name, pack_level, main_topic_color, 'parameters', offset)
            
            # generators
            generators = pack_entry['generators']
            if len(generators) == 0:
                no_such_objects.append('generators')
            else:
                __print_line_header(main_topic_color)
                print_element_breadcumb(pack_name, pack_level, 'generators')
                cprint(' (%d)' % len(generators), color='magenta')
                for gname, generator in generators.items():
                    __print_line_header(main_topic_color)
                    cprint('  - ', end='')
                    cprint('generators > %-15s' % gname.split(os.sep)[-1], color='cyan', end='')
                    cprint(' generate_if=%s' % generator.generate_if)
            
            # Display what the pack do not manage (for info)
            if no_such_objects:
                __print_line_header(main_topic_color)
                cprint(' * The pack do not provide objects: %s' % ','.join(no_such_objects), color='grey')
            cprint('')


def do_packs_list():
    from opsbro.packer import packer
    packs = packer.get_packs()
    all_pack_names = set()
    for (level, packs_in_level) in packs.items():
        for (pname, _) in packs_in_level.items():
            all_pack_names.add(pname)
    
    print_h2('Legend (topics)')
    for topic_id in VERY_ALL_TOPICS:
        color_id = topiker.get_color_id_by_topic_id(topic_id)
        label = TOPICS_LABELS[topic_id]
        s = u'%s %s %s' % (CHARACTERS.topic_small_picto, CHARACTERS.arrow_left, label)
        color_s = lolcat.get_line(s, color_id, spread=None)
        cprint(color_s)
    
    print_h1('Packs')
    
    pnames = list(all_pack_names)
    pnames.sort()
    for pname in pnames:
        present_before = False
        keywords = []  # useless but make lint code check happy
        for level in ('core', 'global', 'zone', 'local'):
            if pname in packs[level]:
                (pack, _) = packs[level][pname]
                if present_before:
                    cprint('(overloaded by %s) ' % CHARACTERS.arrow_left, color='green', end='')
                __print_pack_breadcumb(pname, level, end='', topic_picto='small')
                keywords = pack['keywords']
            present_before = True
        cprint('[keywords: %s]' % (','.join(keywords)), color='magenta')


def do_overload(pack_full_id, to_level='local'):
    from opsbro.packer import packer
    packs = packer.get_packs()
    pack_level, pack_name = __split_pack_full_id(pack_full_id)
    
    if pack_level not in ['core', 'global', 'zone']:
        logger.error('The pack level %s is not valid for the pack overload.' % pack_level)
        sys.exit(2)
    packs_from_level = packs[pack_level]
    if pack_name not in packs_from_level:
        logger.error('The pack %s is not known in the pack level %s' % (pack_name, pack_level))
        sys.exit(2)
    package_data, dir_name = packs[pack_level][pack_name]
    
    if to_level not in ['global', 'zone', 'local']:
        logger.error('The destination pack level %s is not valid for the pack overload.' % to_level)
        sys.exit(2)
    
    dest_dir = __get_pack_directory(to_level, pack_name)
    
    if os.path.exists(dest_dir):
        logger.error('The pack destination directory %s is already exiting. Please delete it first.' % dest_dir)
        sys.exit(2)
    # Ok now really copy it
    try:
        shutil.copytree(dir_name, dest_dir)
    except Exception as exp:
        logger.error('The pack overload did fail (from %s to %s) : %s' % (dir_name, dest_dir, exp))
        sys.exit(2)
    cprint(u'SUCCESS: ', color='green', end='')
    cprint('Pack ', end='')
    cprint('%s (%s)' % (pack_name, dir_name), color='green', end='')
    cprint(' is now overload at level ', end='')
    cprint(' %s (%s)' % (to_level, dest_dir), color='magenta')


def __get_path_pname_from_parameter_full_path(parameter_full_path):
    pack_level, pack_name, parameter_name = __split_parameter_full_path(parameter_full_path)
    pack_root_dir = __get_pack_directory(pack_level, pack_name)
    parameters_file_path = os.path.join(pack_root_dir, 'parameters', 'parameters.yml')
    return parameters_file_path, parameter_name


def do_parameters_set(parameter_full_path, str_value):
    parameters_file_path, parameter_name = __get_path_pname_from_parameter_full_path(parameter_full_path)
    
    yml_parameter_set(parameters_file_path, parameter_name, str_value, file_display=parameter_full_path)
    return


def do_parameters_get(parameter_full_path):
    parameters_file_path, parameter_name = __get_path_pname_from_parameter_full_path(parameter_full_path)
    
    yml_parameter_get(parameters_file_path, parameter_name, file_display=parameter_full_path)
    return


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
        'description': 'Overload (copy in a more priority pack level) a pack. For example copy a pack from the global level to the local one.'
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
