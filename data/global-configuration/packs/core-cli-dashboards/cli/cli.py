# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

import sys
import time
import base64

from opsbro.cli import post_opsbro_json

from opsbro.characters import CHARACTERS
from opsbro.log import cprint, sprintf, logger
from opsbro.cli_display import print_h1
from opsbro.cli import wait_for_agent_started
from opsbro.packer import packer
from opsbro.misc.lolcat import lolcat
from opsbro.topic import topiker

from dashing import HSplit, HBrailleFilledChart, HGauge, VSplit, VDonut, Text


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


def _get_expr_evaluator(expr):
    this_expr = expr
    
    
    def _get_value_from_expression():
        logger.debug('\n\n\n\n\n\n\n\n\n\nEVAL EXPR %s\n\n' % this_expr)
        expr_64 = base64.b64encode(this_expr)
        try:
            r = post_opsbro_json('/agent/evaluator/eval', {'expr': expr_64})
        except Exception, exp:
            logger.debug('\n\n\n\n\n\n\n\n\n\nExcep Result %s => %s\n\n' % (this_expr, exp))
            r = None
        logger.debug('\n\n\n\n\n\n\n\nResult %s => %s\n\n' % (this_expr, r))
        return r
    
    
    return _get_value_from_expression


COLOR_CYAN_ID = 6


def _get_tree(root):
    if not isinstance(root, dict):
        raise Exception('Bad dashboard value definition, should be a dict/hash key. %s found ' % type(root))
    
    if len(root.keys()) != 1:
        raise Exception('Your dashboard object is invalid. Must have ony one key. %s' % root)
    
    root_type = root.keys()[0]
    root_value = root[root_type]
    
    res = None
    # some types are list based, some others are finals (leaf)
    if root_type == 'horizontal_split':
        if not isinstance(root_value, list):
            raise Exception('horizontal_split values must be a list, %s found' % (type(root_value)))
        sons = [_get_tree(son) for son in root_value]
        res = HSplit(*sons)
    elif root_type == 'vertical_split':
        if not isinstance(root_value, list):
            raise Exception('vertical_split values must be a list, %s found' % (type(root_value)))
        sons = [_get_tree(son) for son in root_value]
        res = VSplit(*sons)
    elif root_type == 'horizontal_gauge':
        title = root_value['title']
        unit = root_value['unit']
        value_expr = root_value['value']
        vcallback = _get_expr_evaluator(value_expr)
        res = HGauge(val=33, border_color=COLOR_CYAN_ID, title=title, vcallback=vcallback, unit=unit)
    elif root_type == 'horizontal_chart':
        title = root_value['title']
        unit = root_value['unit']
        value_expr = root_value['value']
        vcallback = _get_expr_evaluator(value_expr)
        res = HBrailleFilledChart(val=33, border_color=COLOR_CYAN_ID, color=2, title=title, vcallback=vcallback, unit=unit)
    elif root_type == 'donut':
        title = root_value['title']
        unit = root_value['unit']
        value_expr = root_value['value']
        vcallback = _get_expr_evaluator(value_expr)
        res = VDonut(val=33, border_color=COLOR_CYAN_ID, title=title, vcallback=vcallback, unit=unit)
    elif root_type == 'text':
        title = root_value['title']
        value_expr = root_value['value']
        vcallback = _get_expr_evaluator(value_expr)
        res = Text(text='bibi', border_color=COLOR_CYAN_ID, title=title, vcallback=vcallback)
    else:
        raise Exception('Unknown dashboard type: %s' % root_type)
    return res


def _get_ui_from_dashboard(dashboard):
    content = dashboard['content']
    
    ui = _get_tree(content)
    return ui


def do_dashboards_show(dashboard_name):
    import codecs
    stdout_utf8 = codecs.getwriter("utf-8")(sys.stdout)
    sys.stdout = stdout_utf8

    wait_for_agent_started(visual_wait=True)
    
    from opsbro.dashboardmanager import get_dashboarder
    dashboarder = get_dashboarder()
    
    dashboard = dashboarder.dashboards.get(dashboard_name, None)
    if dashboard is None:
        logger.error('There is no such dashboard %s. Please use the dashboards list command to view all available dashboards' % dashboard_name)
        sys.exit(2)
    
    ui = _get_ui_from_dashboard(dashboard)
    
    if ui is None:
        sys.exit(1)
    
    while True:
        try:
            ui.display(dashboard['title'])
            time.sleep(10)
        except KeyboardInterrupt:
            # Clean the screen before exiting
            cprint('\033c')
            sys.exit(0)


def do_dashboards_list():
    from opsbro.dashboardmanager import get_dashboarder
    dashboarder = get_dashboarder()
    
    print_h1('Dashboards')
    
    dashboards = dashboarder.dashboards
    
    if len(dashboards) == 0:
        cprint('No dashboards', color='grey')
        sys.exit(0)
    
    packs = {}
    for (dname, dashboard) in dashboards.iteritems():
        pack_name = dashboard['pack_name']
        if pack_name not in packs:
            packs[pack_name] = {}
        packs[pack_name][dname] = dashboard
    pnames = packs.keys()
    pnames.sort()
    for pname in pnames:
        pack_entries = packs[pname]
        cprint('* Pack %s' % pname, color='blue')
        dnames = pack_entries.keys()
        dnames.sort()
        for dname in dnames:
            dashboard = pack_entries[dname]
            level = dashboard['pack_level']
            __print_pack_breadcumb(pname, level, end='', topic_picto='small')
            cprint('%-20s ' % dname, color='magenta', end='')
            cprint(dashboard['title'], color='grey')


exports = {
    
    do_dashboards_show: {
        'keywords'   : ['dashboards', 'show'],
        'args'       : [
            {'name': 'dashboard_name', 'description': 'Dashboard name'},
        ],
        'description': 'Show a specific dashboard'
    },
    
    do_dashboards_list: {
        'keywords'   : ['dashboards', 'list'],
        'args'       : [
        ],
        'description': 'List dashboards'
    },
    
}
