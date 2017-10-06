# -*- coding: utf-8 -*-

from opsbro.log import cprint, logger
from opsbro.characters import CHARACTERS
from opsbro.yamlmgr import yamler


# raw_title means do not format it, use it's own color
def print_h1(title, raw_title=False, only_first_part=False, line_color='cyan', title_color='yellow'):
    p1 = 12
    # 4.5= enter add 4, exit 5, so if enter == exit, will be 4.5 in avg.
    l_title = len(title) - int(title.count(u'\x1b[') * 4.5)
    p2 = l_title + 2  # +2 for spaces around the title
    p3 = 80 - p1 - p2
    
    cprint(CHARACTERS.hbar * p1, color=line_color, end='')
    if not raw_title:
        cprint(' %s ' % title, color=title_color, end='')
    else:
        cprint(' ' + title + ' ', end='')
    if not only_first_part:
        cprint(CHARACTERS.hbar * p3, color=line_color)
    else:
        cprint('')


# raw_title means do not format it, use it's own color
def print_h2(title, raw_title=False):
    cprint(CHARACTERS.hbar_dotted * 12, color='cyan', end='')
    if not raw_title:
        cprint(' %s ' % title, color='yellow')
    else:
        cprint(' ' + title + ' ')


# raw_title means do not format it, use it's own color
def print_h3(title, raw_title=False):
    cprint(u'*', color='cyan', end='')
    if not raw_title:
        cprint(' %s ' % title, color='yellow')
    else:
        cprint(' ' + title + ' ')


def print_element_breadcumb(pack_name, pack_level, what, name='', set_pack_color=False):
    star = ' * '
    if set_pack_color:
        cprint(star, end='')
    else:
        cprint(star, color='grey', end='')
    level_color = 'blue' if set_pack_color else 'grey'
    cprint(pack_level, color=level_color, end='')
    dash = ' > '
    if set_pack_color:
        cprint(dash, end='')
    else:
        cprint(dash, color='grey', end='')
    name_color = 'yellow' if set_pack_color else 'grey'
    cprint(pack_name, color=name_color, end='')
    cprint(' > ', end='')
    cprint(what, color='cyan', end='')
    if name:
        cprint(' > ', end='')
        cprint(name, color='magenta', end='')


def __assert_pname_in_obj(pname, o, parameters_file_path):
    if pname not in o:
        err = 'Cannot find the parameter %s in the parameters file %s' % (pname, parameters_file_path)
        logger.error(err)
        raise Exception(err)


def yml_parameter_get(parameters_file_path, parameter_name, file_display=None):
    if file_display is None:
        file_display = parameters_file_path
    o = yamler.get_object_from_parameter_file(parameters_file_path)
    
    # Error if the parameter is not present
    __assert_pname_in_obj(parameter_name, o, parameters_file_path)
    
    # yaml.dumps is putting us a ugly '...' as last line, remove it
    lines = yamler.dumps(o[parameter_name]).splitlines()
    if '...' in lines:
        lines.remove('...')
    
    value_string = '\n'.join(lines)
    cprint('%s' % file_display, color='magenta', end='')
    cprint(' %s ' % CHARACTERS.arrow_left, end='')
    cprint(value_string, color='green')
    
    # Now if there are, get the comments
    comment = yamler.get_key_comment(o, parameter_name)
    if comment is not None:
        lines = comment.splitlines()
        for line in lines:
            cprint('  | %s' % line, color='grey')


def __get_and_assert_valid_to_yaml_value(str_value):
    try:
        python_value = yamler.loads('%s' % str_value)
    except Exception, exp:
        err = 'Cannot load the value %s as a valid parameter: %s' % (str_value, exp)
        logger.error(err)
        raise Exception(err)
    return python_value


def yml_parameter_set(parameters_file_path, parameter_name, str_value, file_display=None):
    python_value = __get_and_assert_valid_to_yaml_value(str_value)
    
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


def yml_parameter_add(parameters_file_path, parameter_name, str_value, file_display=None):
    python_value = __get_and_assert_valid_to_yaml_value(str_value)
    
    if file_display is None:
        file_display = parameters_file_path
    
    # First get the value
    o = yamler.get_object_from_parameter_file(parameters_file_path)
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
    python_value = __get_and_assert_valid_to_yaml_value(str_value)
    
    if file_display is None:
        file_display = parameters_file_path
    
    # First get the value
    o = yamler.get_object_from_parameter_file(parameters_file_path)
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


_donut_100 = u'''
 ⢀⣤⣶⣿⣿⣿⣷⣦⣄
⢰⣿⣿⣿⠿⠛⠻⢿⣿⣿⣷
⣿⣿⣿⠃ XXX⢻⣿⣿⡇
⢿⣿⣿⣆ Y ⢀⣾⣿⣿⠇
⠘⢿⣿⣿⣿⣶⣾⣿⣿⣿⠟
  ⠙⠿⣿⣿⣿⡿⠟⠁
'''.replace('XXX', r'%3d').replace('Y', r'%%')

_donut_95_99 = u'''
 ⢀⣤⣶⣿ ⣿⣷⣦⣄
⢰⣿⣿⣿⠿ ⠻⢿⣿⣿⣷
⣿⣿⣿⠃ XX ⢻⣿⣿⡇
⢿⣿⣿⣆ Y ⢀⣾⣿⣿⠇
⠘⢿⣿⣿⣿⣶⣾⣿⣿⣿⠟
  ⠙⠿⣿⣿⣿⡿⠟⠁
'''.replace('XX', r'%2d').replace('Y', r'%%')

_donut_90_95 = u'''
 ⢀⣤⣶  ⣿⣷⣦⣄
⢰⣿⣿⣿⠿ ⠻⢿⣿⣿⣷
⣿⣿⣿⠃ XX ⢻⣿⣿⡇
⢿⣿⣿⣆ Y ⢀⣾⣿⣿⠇
⠘⢿⣿⣿⣿⣶⣾⣿⣿⣿⠟
  ⠙⠿⣿⣿⣿⡿⠟⠁
'''.replace('XX', r'%2d').replace('Y', r'%%')

_donut_85_90 = u'''
 ⢀⣤   ⣿⣷⣦⣄
⢰⣿⣿⣿  ⠻⢿⣿⣿⣷
⣿⣿⣿⠃ XX ⢻⣿⣿⡇
⢿⣿⣿⣆ Y ⢀⣾⣿⣿⠇
⠘⢿⣿⣿⣿⣶⣾⣿⣿⣿⠟
  ⠙⠿⣿⣿⣿⡿⠟⠁
'''.replace('XX', r'%2d').replace('Y', r'%%')

_donut_80_85 = u'''
      ⣿⣷⣦⣄
⢰⣿⣆   ⠻⢿⣿⣿⣷
⣿⣿⣿⠃ XX ⢻⣿⣿⡇
⢿⣿⣿⣆ Y ⢀⣾⣿⣿⠇
⠘⢿⣿⣿⣿⣶⣾⣿⣿⣿⠟
  ⠙⠿⣿⣿⣿⡿⠟⠁
'''.replace('XX', r'%2d').replace('Y', r'%%')

_donut_75_80 = u'''
      ⣿⣷⣦⣄
⡀     ⠻⢿⣿⣿⣷
⣿⣶⣆  XX ⢻⣿⣿⡇
⢿⣿⣿⣆ Y ⢀⣾⣿⣿⠇
⠘⢿⣿⣿⣿⣶⣾⣿⣿⣿⠟
  ⠙⠿⣿⣿⣿⡿⠟⠁
'''.replace('XX', r'%2d').replace('Y', r'%%')

_donut_70_75 = u'''
      ⣿⣷⣦⣄
      ⠻⢿⣿⣿⣷
     XX ⢻⣿⣿⡇
⢿⣿⣿⣆ Y ⢀⣾⣿⣿⠇
⠘⢿⣿⣿⣿⣶⣾⣿⣿⣿⠟
  ⠙⠿⣿⣿⣿⡿⠟⠁
'''.replace('XX', r'%2d').replace('Y', r'%%')

_donut_65_70 = u'''
      ⣿⣷⣦⣄
      ⠻⢿⣿⣿⣷
     XX ⢻⣿⣿⡇
     Y ⢀⣾⣿⣿⠇
 ⣤⣶⣿⣿⣶⣾⣿⣿⣿⠟
  ⠙⠿⣿⣿⣿⡿⠟⠁
'''.replace('XX', r'%2d').replace('Y', r'%%')

_donut_60_65 = u'''
      ⣿⣷⣦⣄
      ⠻⢿⣿⣿⣷
     XX ⢻⣿⣿⡇
     Y ⢀⣾⣿⣿⠇
   ⣠⣾⣶⣾⣿⣿⣿⠟
  ⠈⠿⣿⣿⣿⡿⠟⠁
'''.replace('XX', r'%2d').replace('Y', r'%%')

_donut_55_60 = u'''
      ⣿⣷⣦⣄
      ⠻⢿⣿⣿⣷
     XX ⢻⣿⣿⡇
     Y ⢀⣾⣿⣿⠇
    ⣰⣶⣾⣿⣿⣿⠟
   ⣰⣿⣿⣿⡿⠟⠁
'''.replace('XX', r'%2d').replace('Y', r'%%')

_donut_50_55 = u'''
      ⣿⣷⣦⣄
      ⠻⢿⣿⣿⣷
     XX ⢻⣿⣿⡇
     Y ⢀⣾⣿⣿⠇
    ⢀⣾⣿⣿⣿⠟
    ⣾⣿⡿⠟⠁
'''.replace('XX', r'%2d').replace('Y', r'%%')

_donut_50 = u'''
      ⣿⣷⣦⣄
      ⠻⢿⣿⣿⣷
     XX ⢻⣿⣿⡇
     Y ⢀⣾⣿⣿⠇
      ⣾⣿⣿⣿⠟
      ⣿⡿⠟⠁
'''.replace('XX', r'%2d').replace('Y', r'%%')

_donut_45_50 = u'''
      ⣿⣷⣦⣄
      ⠻⢿⣿⣿⣷
     XX ⢻⣿⣿⡇
     Y ⢀⣾⣿⣿⠇
      ⣾⣿⣿⣿⠟
       ⢻⠟⠁
'''.replace('XX', r'%2d').replace('Y', r'%%')

_donut_40_45 = u'''
      ⣿⣷⣦⣄
      ⠻⢿⣿⣿⣷
     XX ⢻⣿⣿⡇
     Y ⢀⣾⣿⣿⠇
       ⢻⣿⣿⠟
        ⠙⠁
'''.replace('XX', r'%2d').replace('Y', r'%%')

_donut_35_40 = u'''
      ⣿⣷⣦⣄
      ⠻⢿⣿⣿⣷
     XX ⢻⣿⣿⡇
     Y ⢀⣾⣿⣿⠇
       ⠙⢻⣿⡟
       
'''.replace('XX', r'%2d').replace('Y', r'%%')

_donut_30_35 = u'''
      ⣿⣷⣦⣄
      ⠻⢿⣿⣿⣷
     XX ⢻⣿⣿⡇
     Y ⢀⣾⣿⣿⠇
       ⠈⠛⠛⠋
       
'''.replace('XX', r'%2d').replace('Y', r'%%')

_donut_25_30 = u'''
      ⣿⣷⣦⣄
      ⠻⢿⣿⣿⣷
     XX ⢻⣿⣿⡇
     Y  ⠈⢻⣿⠇
     

'''.replace('XX', r'%2d').replace('Y', r'%%')

_donut_25 = u'''
      ⣿⣷⣦⣄
      ⠻⢿⣿⣿⣷
     XX ⢻⣿⣿⡇
     Y
     
     
'''.replace('XX', r'%2d').replace('Y', r'%%')

_donut_20_25 = u'''
      ⣿⣷⣦⣄
      ⠻⢿⣿⣿⣷
     XX ⢻⡿⠟⠁
     Y
     
     
'''.replace('XX', r'%2d').replace('Y', r'%%')

_donut_15_20 = u'''
      ⣿⣷⣦⣄
      ⠻⢿⡿⠋
     XX
     Y
     
     
'''.replace('XX', r'%2d').replace('Y', r'%%')

_donut_10_15 = u'''
      ⣿⣷⣦
      ⠻⡿⠋
     XX
     Y
     
     
'''.replace('XX', r'%2d').replace('Y', r'%%')

_donut_5_10 = u'''
      ⣿⣦
      ⠛⠋
     XX
     Y
     
     
'''.replace('XX', r'%2d').replace('Y', r'%%')

_donut_0_5 = u'''
      ⣿
      ⠛
     XX
     Y
     
     
'''.replace('XX', r'%2d').replace('Y', r'%%')

_donut_0 = u'''

   
     XX
     Y


'''.replace('XX', r'%2d').replace('Y', r'%%')


class DonutPrinter(object):
    def get_donut(self, value):
        
        try:
            if 0 < value < 1:  # round 0
                value = 0
            elif 100 <= value < 101:  # get round for 100
                value = 100
            else:
                value = int(value)
        except Exception:
            return
        if value < 0:
            return
        if value > 100:
            return
        
        if value == 0:
            tpl = _donut_0
        elif 0 < value <= 5:
            tpl = _donut_0_5
        elif 5 < value <= 10:
            tpl = _donut_5_10
        elif 10 < value <= 15:
            tpl = _donut_10_15
        elif 15 < value <= 20:
            tpl = _donut_15_20
        elif 20 < value <= 25:
            tpl = _donut_20_25
        elif value == 25:
            tpl = _donut_25
        elif 25 < value <= 30:
            tpl = _donut_25_30
        elif 30 < value <= 35:
            tpl = _donut_30_35
        elif 35 < value <= 40:
            tpl = _donut_35_40
        elif 40 < value <= 45:
            tpl = _donut_40_45
        elif 45 < value <= 49:
            tpl = _donut_45_50
        elif value == 50:
            tpl = _donut_50
        elif 50 < value <= 55:
            tpl = _donut_50_55
        elif 55 < value <= 60:
            tpl = _donut_55_60
        elif 60 < value <= 65:
            tpl = _donut_60_65
        elif 65 < value <= 70:
            tpl = _donut_65_70
        elif 70 < value <= 75:
            tpl = _donut_70_75
        elif 75 < value <= 80:
            tpl = _donut_75_80
        elif 80 < value <= 85:
            tpl = _donut_80_85
        elif 85 < value <= 90:
            tpl = _donut_85_90
        elif 90 < value <= 95:
            tpl = _donut_90_95
        elif 95 < value <= 99:
            tpl = _donut_95_99
        elif value == 100:
            tpl = _donut_100
        
        res = tpl % value
        # Remove the first return line (use for code lisibility)
        res = '\n'.join(res.splitlines()[1:])
        return res
