# -*- coding: utf-8 -*-

import sys

from .log import cprint, logger
from .characters import CHARACTERS
from .yamlmgr import yamler
from .defaultpaths import DEFAULT_CFG_FILE
from .cli import get_opsbro_json, put_opsbro_json
from .unixclient import get_request_errors
from .util import bytes_to_unicode

# some parameters cannot be "set", only add/remove
list_type_parameters = ('groups', 'seeds')


def __assert_pname_in_obj(pname, o, parameters_file_path):
    if pname not in o:
        err = 'Cannot find the parameter "%s" in the parameters file "%s"' % (pname, parameters_file_path)
        logger.error(err)
        raise Exception(err)


def yml_parameter_get(parameters_file_path, parameter_name, file_display=None):
    if file_display is None:
        file_display = parameters_file_path
    o = yamler.get_object_from_parameter_file(parameters_file_path, with_comments=True)  # in CLI comments are importants
    
    # Error if the parameter is not present
    __assert_pname_in_obj(parameter_name, o, parameters_file_path)
    
    # yaml.dumps is putting us a ugly '...' as last line, remove it, and be sure to have unicode
    lines = yamler.dumps(o[parameter_name]).splitlines()
    lines = [bytes_to_unicode(line) for line in lines if lines != u'...']
    
    value_string = u'\n'.join(lines)
    cprint('%s' % file_display, color='magenta', end='')
    cprint(' %s ' % CHARACTERS.arrow_left, end='')
    cprint(value_string, color='green')
    
    # Now if there are, get the comments
    comment = yamler.get_key_comment(o, parameter_name)
    if comment is not None:
        lines = comment.splitlines()
        for line in lines:
            cprint('  | %s' % line, color='grey')


def get_and_assert_valid_to_yaml_value(str_value):
    try:
        python_value = yamler.loads('%s' % str_value)
    except Exception as exp:
        err = 'Cannot load the value %s as a valid parameter: %s' % (str_value, exp)
        logger.error(err)
        raise Exception(err)
    return python_value


def yml_parameter_set(parameters_file_path, parameter_name, str_value, file_display=None):
    python_value = get_and_assert_valid_to_yaml_value(str_value)
    
    if file_display is None:
        file_display = parameters_file_path
    
    # Ok write it
    yamler.set_value_in_parameter_file(parameters_file_path, parameter_name, python_value, str_value)
    
    cprint('OK: ', color='green', end='')
    cprint('%s (%s)' % (file_display, parameters_file_path), color='magenta', end='')
    cprint(' SET ', end='')
    cprint(parameter_name, color='magenta', end='')
    cprint(' %s ' % CHARACTERS.arrow_left, end='')
    cprint(str_value, color='green')


def parameter_add_to_main_yml(parameter_name, str_value):
    if parameter_name not in list_type_parameters:
        cprint('Error: the parameter %s is not a list. Cannot use the add/remove. Please use set instead' % parameter_name)
        sys.exit(2)
    parameters_file_path = DEFAULT_CFG_FILE
    yml_parameter_add(parameters_file_path, parameter_name, str_value, file_display='agent.%s' % parameter_name)
    # Groups is a bit special as it can be load directly by the agent
    if parameter_name == 'groups':
        try:
            did_change = get_opsbro_json('/agent/parameters/add/groups/%s' % str_value)
        except get_request_errors():
            cprint('  | The agent seems to not be started. Skipping hot group addition.', color='grey')
            return
        if did_change:
            cprint("  | The agent groups are updated too. You don't need to restart your daemon.", color='grey')
        return
    cprint('NOTE: only the yml configuration file is modified. You need to restart your agent to use this modification', color='grey')


def parameter_remove_to_main_yml(parameter_name, str_value):
    if parameter_name not in list_type_parameters:
        cprint('Error: the parameter %s is not a list. Cannot use the add/remove. Please use set instead' % parameter_name)
        sys.exit(2)
    parameters_file_path = DEFAULT_CFG_FILE
    yml_parameter_remove(parameters_file_path, parameter_name, str_value, file_display='agent.%s' % parameter_name)
    # Groups is a bit special as it can be load directly by the agent
    if parameter_name == 'groups':
        try:
            did_change = get_opsbro_json('/agent/parameters/remove/groups/%s' % str_value)
        except get_request_errors():
            cprint('  | The agent seems to not be started. Skipping hot group removing.', color='grey')
            return
        if did_change:
            cprint("  | The agent groups are updated too. You don't need to restart your daemon.", color='grey')
        return
    cprint('NOTE: only the yml configuration file is modified. You need to restart your agent to use this modification', color='grey')


def parameter_set_to_main_yml(parameter_name, str_value):
    if parameter_name in list_type_parameters:
        cprint('Error: the parameter %s is a list. Cannot use the set. Please use add/remove instead' % parameter_name)
        sys.exit(2)
    parameters_file_path = DEFAULT_CFG_FILE
    
    # Maybe the parameter can be wrong (based on the current configuration)
    if parameter_name == 'zone':
        from .zonemanager import zonemgr
        zones_names = zonemgr.get_zones_names()
        zones_names.sort()
        if str_value not in zones_names:
            cprint('ERROR: The zone %s is unknown. The known zones are: %s' % (str_value, ','.join(zones_names)), color='red')
            sys.exit(2)
    
    # If ok can be set
    yml_parameter_set(parameters_file_path, parameter_name, str_value, file_display='agent.%s' % parameter_name)
    
    # Zone can be hot changed
    if parameter_name == 'zone':
        cprint("Switching to zone %s" % str_value)
        try:
            r = put_opsbro_json('/agent/zone', str_value)
        except get_request_errors():
            cprint('  | The agent seems to not be started. Skipping hot zone change.', color='grey')
            return
        if not r['success']:
            cprint('ERROR: %s' % r['text'], color='red')
            sys.exit(2)
        did_change = r['did_change']
        if did_change:
            cprint("  | The agent zone is updated too. You don't need to restart your daemon.", color='grey')
        return
    
    cprint('NOTE: only the yml configuration file is modified. You need to restart your agent to use this modification', color='grey')


def yml_parameter_add(parameters_file_path, parameter_name, str_value, file_display=None):
    python_value = get_and_assert_valid_to_yaml_value(str_value)
    
    if file_display is None:
        file_display = parameters_file_path
    
    # First get the value
    o = yamler.get_object_from_parameter_file(parameters_file_path, with_comments=True)  # in CLI comments are importants
    # Error if the parameter is not present
    __assert_pname_in_obj(parameter_name, o, parameters_file_path)
    
    current_value = o[parameter_name]
    
    if not isinstance(current_value, list):
        err = 'Error: the property %s is not a list. Cannot add a value to it. (current value=%s)' % (parameter_name, current_value)
        raise Exception(err)
    
    # Maybe it's not need
    if python_value not in current_value:
        # Update the current_value in place, not a problem
        current_value.append(python_value)
        # Ok write it
        yamler.set_value_in_parameter_file(parameters_file_path, parameter_name, current_value, str_value, change_type='ADD')
        state = 'OK'
    else:
        state = 'OK(already set)'
    
    cprint('%s: ' % state, color='green', end='')
    cprint('%s (%s)' % (file_display, parameters_file_path), color='magenta', end='')
    cprint(' ADD ', end='')
    cprint(parameter_name, color='magenta', end='')
    cprint(' %s ' % CHARACTERS.arrow_left, end='')
    cprint(str_value, color='green')


def yml_parameter_remove(parameters_file_path, parameter_name, str_value, file_display=None):
    python_value = get_and_assert_valid_to_yaml_value(str_value)
    
    if file_display is None:
        file_display = parameters_file_path
    
    # First get the value
    o = yamler.get_object_from_parameter_file(parameters_file_path, with_comments=True)  # in CLI comments are importants
    # Error if the parameter is not present
    __assert_pname_in_obj(parameter_name, o, parameters_file_path)
    
    current_value = o[parameter_name]
    
    if not isinstance(current_value, list):
        err = 'Error: the property %s is not a list. Cannot remove a value to it. (current value=%s)' % (parameter_name, current_value)
        raise Exception(err)
    
    # Maybe it was not in it, not a real problem in fact
    
    if python_value in current_value:
        current_value.remove(python_value)
        # Ok write it
        yamler.set_value_in_parameter_file(parameters_file_path, parameter_name, current_value, str_value, change_type='ADD')
        state = 'OK'
    else:
        state = 'OK(was not set)'
    
    cprint('%s: ' % state, color='green', end='')
    cprint('%s (%s)' % (file_display, parameters_file_path), color='magenta', end='')
    cprint(' REMOVE ', end='')
    cprint(parameter_name, color='magenta', end='')
    cprint(' %s ' % CHARACTERS.arrow_left, end='')
    cprint(str_value, color='green')
