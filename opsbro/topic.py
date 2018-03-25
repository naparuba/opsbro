# -*- coding: utf-8 -*-

import random
import itertools

from .misc.lolcat import lolcat

TOPIC_SERVICE_DISCOVERY = 0x1 << 0
TOPIC_AUTOMATIC_DECTECTION = 0x1 << 1
TOPIC_MONITORING = 0x1 << 2
TOPIC_METROLOGY = 0x1 << 3
TOPIC_CONFIGURATION_AUTOMATION = 0x1 << 4
TOPIC_SYSTEM_COMPLIANCE = 0x1 << 5
TOPIC_GENERIC = 0x1 << 6  # hidden one, for other stuff

TOPICS = [TOPIC_SERVICE_DISCOVERY, TOPIC_AUTOMATIC_DECTECTION, TOPIC_MONITORING, TOPIC_METROLOGY,
          TOPIC_CONFIGURATION_AUTOMATION, TOPIC_SYSTEM_COMPLIANCE]

VERY_ALL_TOPICS = TOPICS[:]
VERY_ALL_TOPICS.append(TOPIC_GENERIC)

TOPICS_LABELS = {
    TOPIC_SERVICE_DISCOVERY       : u'service discovery',
    TOPIC_AUTOMATIC_DECTECTION    : u'automatic detection',
    TOPIC_MONITORING              : u'monitoring',
    TOPIC_METROLOGY               : u'metrology',
    TOPIC_CONFIGURATION_AUTOMATION: u'configuration automation',
    TOPIC_SYSTEM_COMPLIANCE       : u'system compliance',
    TOPIC_GENERIC                 : u'generic',
}

TOPIC_ID_BY_STRING = {
    u'service discovery'       : TOPIC_SERVICE_DISCOVERY,
    u'automatic detection'     : TOPIC_AUTOMATIC_DECTECTION,
    u'monitoring'              : TOPIC_MONITORING,
    u'metrology'               : TOPIC_METROLOGY,
    u'configuration automation': TOPIC_CONFIGURATION_AUTOMATION,
    u'system compliance'       : TOPIC_SYSTEM_COMPLIANCE,
    u'generic'                 : TOPIC_GENERIC,
}

# Size of configuration automation for aligment display
MAX_TOPICS_LABEL_SIZE = 26

TOPICS_LABEL_BANNER = {
    TOPIC_SERVICE_DISCOVERY       : u'┏ service discovery',
    TOPIC_AUTOMATIC_DECTECTION    : u'┗ automatic detection',
    TOPIC_MONITORING              : u'┏ monitoring',
    TOPIC_METROLOGY               : u'┗ metrology',
    TOPIC_CONFIGURATION_AUTOMATION: u'┏ configuration automation',
    TOPIC_SYSTEM_COMPLIANCE       : u'┗ system compliance',
}

TOPICS_SUB_TITLES = {
    TOPIC_SERVICE_DISCOVERY       : u'Is there any new servers spawn last few seconds?',
    TOPIC_AUTOMATIC_DECTECTION    : u'Is my server linux or windows, mongodb or redis?',
    TOPIC_MONITORING              : u'Is all OK on my server and applications?',
    TOPIC_METROLOGY               : u'Is my server and application performing well?',
    TOPIC_CONFIGURATION_AUTOMATION: u'Install+configure apache+nginx if server in web group',
    TOPIC_SYSTEM_COMPLIANCE       : u'Are the security patches applied?',
}

# sort of blue
DEFAULT_COLOR_ID = 40

TOPICS_COLORS = {
    # light Purple
    TOPIC_SERVICE_DISCOVERY       : 26,
    
    # pale purple
    TOPIC_AUTOMATIC_DECTECTION    : 30,
    
    # light green
    TOPIC_MONITORING              : 53,
    
    # pastel green
    TOPIC_METROLOGY               : 57,
    
    # couleur peau
    TOPIC_CONFIGURATION_AUTOMATION: 12,
    
    # jaune sombre
    TOPIC_SYSTEM_COMPLIANCE       : 8,
    
    # Other?
    TOPIC_GENERIC                 : DEFAULT_COLOR_ID,
}

_TOPICS_COLORS_VALUES = TOPICS_COLORS.values()
random.shuffle(_TOPICS_COLORS_VALUES)
TOPICS_COLORS_RANDOM_VALUES_LOOP = itertools.cycle(_TOPICS_COLORS_VALUES)


# Yes, there is a pokemon word play with a french pokemon. I love pokemon and my son too. Deal with it ( •_•)      ( •_•)>⌐■-■       (⌐■_■)
class Topiker(object):
    def __init__(self):
        self.topic_enabled = {}
        for topic in TOPICS:
            self.topic_enabled[topic] = True
    
    
    def get_topic_states(self):
        return self.topic_enabled
    
    
    def set_topic_state(self, topic, state):
        if topic not in TOPICS:
            raise Exception('The topic %s is not an allowed one' % topic)
        self.topic_enabled[topic] = state
    
    
    def is_topic_enabled(self, topic):
        if topic not in TOPICS:
            raise Exception('The topic %s is not an allowed one' % topic)
        return self.topic_enabled[topic]
    
    
    def get_color_id_by_topic_string(self, topic_s):
        if topic_s not in TOPIC_ID_BY_STRING:
            return DEFAULT_COLOR_ID
        topic_id = TOPIC_ID_BY_STRING[topic_s]
        color_id = TOPICS_COLORS[topic_id]
        return color_id
    
    
    def get_color_id_by_topic_id(self, topic_id):
        color_id = TOPICS_COLORS[topic_id]
        return color_id
    
    
    def get_colorized_topic_from_string(self, topic_s):
        color_id = self.get_color_id_by_topic_string(topic_s)
        r = lolcat.get_line(topic_s, color_id, spread=None)
        return r


topiker = Topiker()
