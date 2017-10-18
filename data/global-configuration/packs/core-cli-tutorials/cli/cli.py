#!/usr/bin/env python

# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com


import sys
import time
from math import ceil

from opsbro.characters import CHARACTERS
from opsbro.log import cprint, sprintf, logger
from opsbro.cli_display import print_h1
from opsbro.packer import packer
from opsbro.misc.lolcat import lolcat
from opsbro.topic import topiker


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


def do_tutorials_list():
    from opsbro.tutorial import tutorialmgr
    
    tutorials = tutorialmgr.tutorials
    
    print_h1('Tutorials')
    
    if len(tutorials) == 0:
        cprint('No tutorials', color='grey')
        sys.exit(0)
    
    packs = {}
    for tutorial in tutorials:
        tutorial_name = tutorial.name
        pack_name = tutorial.pack_name
        if pack_name not in packs:
            packs[pack_name] = {}
        packs[pack_name][tutorial_name] = tutorial
    pnames = packs.keys()
    pnames.sort()
    for pname in pnames:
        pack_entries = packs[pname]
        tnames = pack_entries.keys()
        tnames.sort()
        for tname in tnames:
            tutorial = pack_entries[tname]
            duration = ceil(tutorial.get_duration())
            level = tutorial.pack_level
            __print_pack_breadcumb(pname, level, end='', topic_picto='small')
            cprint(' %-20s ' % tname, color='magenta', end='')
            cprint(' (Duration: %ds) ' % duration, end='')
            cprint(tutorial.title, color='grey')


def do_tutorial_show(tutorial_name):
    from opsbro.tutorial import tutorialmgr
    
    tutorials = tutorialmgr.tutorials
    tutorial = None
    for tuto in tutorials:
        if tuto.name == tutorial_name:
            tutorial = tuto
            break
    if tutorial is None:
        logger.error('Cannot find the tutorial %s' % tutorial_name)
        sys.exit(2)
    tuto_data = tutorial.get_tutorial_data()
    stdout_entries = tuto_data['stdout']
    cprint('\n\nTutorial is starting:', color='magenta')
    cprint(' | please note that is is only a screencast and nothing will be executed or changed in your system.\n\n', color='grey')
    
    for e in stdout_entries:
        wait_time = e[0]
        line = e[1]
        cprint(line, end='')
        sys.stdout.flush()
        time.sleep(wait_time)
    
    cprint('\n\nTutorial is ended', color='magenta')


exports = {
    do_tutorials_list: {
        'keywords'   : ['tutorials', 'list'],
        'args'       : [
        ],
        'description': 'List available tutorials'
    },
    do_tutorial_show : {
        'keywords'   : ['tutorials', 'show'],
        'args'       : [
            {'name': 'tutorial-name', 'description': 'Name of the tutorial to show'},
        ],
        'description': 'Show a tutorial in your terminal (note that no action will be done, all is fake)'
    },
    
}
