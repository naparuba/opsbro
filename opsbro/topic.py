# -*- coding: utf-8 -*-

TOPIC_SERVICE_DISCOVERY = 0x1 << 0
TOPIC_AUTOMATIC_DECTECTION = 0x1 << 1
TOPIC_MONITORING = 0x1 << 2
TOPIC_METROLOGY = 0x1 << 3
TOPIC_CONFIGURATION_AUTOMATION = 0x1 << 4
TOPIC_SYSTEM_COMPLIANCE = 0x1 << 5

TOPICS = [TOPIC_SERVICE_DISCOVERY, TOPIC_AUTOMATIC_DECTECTION, TOPIC_MONITORING, TOPIC_METROLOGY,
          TOPIC_CONFIGURATION_AUTOMATION, TOPIC_SYSTEM_COMPLIANCE]

TOPICS_LABELS = {
    TOPIC_SERVICE_DISCOVERY       : u'service discovery',
    TOPIC_AUTOMATIC_DECTECTION    : u'automatic detection',
    TOPIC_MONITORING              : u'monitoring',
    TOPIC_METROLOGY               : u'metrology',
    TOPIC_CONFIGURATION_AUTOMATION: u'configuration automation',
    TOPIC_SYSTEM_COMPLIANCE       : u'system compliance',
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
    TOPIC_SYSTEM_COMPLIANCE       : u'Are the secutiry patches applied?',
}

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
}
