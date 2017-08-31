# -*- coding: utf-8 -*-

from opsbro.log import cprint, logger


# raw_title means do not format it, use it's own color
def print_h1(title, raw_title=False, only_first_part=False, line_color='cyan', title_color='yellow'):
    p1 = 12
    # 4.5= enter add 4, exit 5, so if enter == exit, will be 4.5 in avg.
    l_title = len(title) - int(title.count(u'\x1b[') * 4.5)
    p2 = l_title + 2  # +2 for spaces around the title
    p3 = 80 - p1 - p2
    
    cprint(u'─' * p1, color=line_color, end='')
    if not raw_title:
        cprint(' %s ' % title, color=title_color, end='')
    else:
        cprint(' ' + title + ' ', end='')
    if not only_first_part:
        cprint(u'─' * p3, color=line_color)
    else:
        cprint('')


# raw_title means do not format it, use it's own color
def print_h2(title, raw_title=False):
    cprint(u'᠁' * 12, color='cyan', end='')
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


def print_element_breadcumb(pack_name, pack_level, what, name=''):
    cprint('  * ', end='')
    cprint(pack_level, color='blue', end='')
    cprint(' > ', end='')
    cprint(pack_name, color='yellow', end='')
    cprint(' > ', end='')
    cprint(what, color='cyan', end='')
    if name:
        cprint(' > ', end='')
        cprint(name, color='magenta', end='')
