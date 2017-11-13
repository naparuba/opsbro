#!/usr/bin/env python
# -*- coding: utf-8 -*- #
from __future__ import unicode_literals

AUTHOR = u'Shinken framework team'
SITENAME = u'Some monitoring guys'
SITEURL = ''

GOOGLE_ANALYTICS_CODE = 'UA-48477803-1'

TIMEZONE = 'Europe/Paris'

DEFAULT_LANG = u'en'

# Feed generation is usually not desired when developing
FEED_ALL_ATOM = None
CATEGORY_FEED_ATOM = None
TRANSLATION_FEED_ATOM = None

# Blogroll
LINKS =  (('shinken project', 'http://www.shinken-monitoring.org/'),
          ('shinken.io', 'http://shinken.io/'),
          ('shinken solutions', 'http://www.shinken-solutions.com/'),
          )

# Social widget
SOCIAL = (('community tweets', 'https://twitter.com/shinken_monitor'),
          ('shinken.io news', 'https://twitter.com/Shinkenio'),
          ('Enterprise news', 'https://twitter.com/ShinkenInc'),
          )

DEFAULT_PAGINATION = 10

# Uncomment following line if you want document-relative URLs when developing
#RELATIVE_URLS = True

#THEME = "theme/ohwait"
THEME = "theme/lannisport"

DEFAULT_DATE_FORMAT = '%b %d, %Y'

ARTICLE_URL = '{slug}/'
ARTICLE_SAVE_AS = '{slug}/index.html'

PAGE_URL = '{slug}.html'
PAGE_SAVE_AS = '{slug}.html'

CATEGORY_SAVE_AS = False
CATEGORIES_SAVE_AS = False
PAGE_LANG_SAVE_AS = False
TAGS_SAVE_AS = False
AUTHOR_SAVE_AS = False
AUTHORS_SAVE_AS = False
ARCHIVES_SAVE_AS = False

MD_EXTENSIONS = ['codehilite(css_class=highlight)']



GITHUB_URL = 'https://github.com/naparuba/shinken'
TWITTER_URL = 'https://twitter.com/shinken_monitor'
