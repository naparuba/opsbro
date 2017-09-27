# -*- coding: utf-8 -*-
import sys

from opsbro.misc.lolcat import lolcat
from opsbro.log import cprint
from opsbro.characters import TEST_CHARS

import time
spinners = [
  #u"←↖↑↗→↘↓↙",
  #u"▁▃▄▅▆▇█▇▆▅▄▃",
  #u"▉▊▋▌▍▎▏▎▍▌▋▊▉",
  #u"▖▘▝▗",
  #u"▌▀▐▄",
  #u"┤┘┴└├┌┬┐",
  #u"◢◣◤◥",
  #u"◰◳◲◱",
  #u"◴◷◶◵",
  #u"◐◓◑◒",
  #u"|/-\\",
  #u".oO@*",
  #[u"◜ ", u" ◝", u" ◞", u"◟ "],
  #u"◇◈◆",
  u"⣾⣽⣻⢿⡿⣟⣯⣷",
  u"⣷⣯⣟⡿⢿⣻⣽⣾",
  #u"⡀⡁⡂⡃⡄⡅⡆⡇⡈⡉⡊⡋⡌⡍⡎⡏⡐⡑⡒⡓⡔⡕⡖⡗⡘⡙⡚⡛⡜⡝⡞⡟⡠⡡⡢⡣⡤⡥⡦⡧⡨⡩⡪⡫⡬⡭⡮⡯⡰⡱⡲⡳⡴⡵⡶⡷⡸⡹⡺⡻⡼⡽⡾⡿⢀⢁⢂⢃⢄⢅⢆⢇⢈⢉⢊⢋⢌⢍⢎⢏⢐⢑⢒⢓⢔⢕⢖⢗⢘⢙⢚⢛⢜⢝⢞⢟⢠⢡⢢⢣⢤⢥⢦⢧⢨⢩⢪⢫⢬⢭⢮⢯⢰⢱⢲⢳⢴⢵⢶⢷⢸⢹⢺⢻⢼⢽⢾⢿⣀⣁⣂⣃⣄⣅⣆⣇⣈⣉⣊⣋⣌⣍⣎⣏⣐⣑⣒⣓⣔⣕⣖⣗⣘⣙⣚⣛⣜⣝⣞⣟⣠⣡⣢⣣⣤⣥⣦⣧⣨⣩⣪⣫⣬⣭⣮⣯⣰⣱⣲⣳⣴⣵⣶⣷⣸⣹⣺⣻⣼⣽⣾⣿",
  u"⠁⠂⠄⡀⢀⠠⠐⠈",
  #[u">))'>", u" >))'>", u"  >))'>", u"   >))'>", u"    >))'>", u"   <'((<", u"  <'((<", u" <'((<"],
]

for l in spinners:
    print "\n ******* "
    if isinstance(l, basestring):
        chars = [c for c in l]
    else:
        chars = l
    cprint(' CHARS: %s' % ''.join(chars))
    for c in chars:
        cprint('\r', end='')
        cprint(' %s' % c, color='blue', end='')
        sys.stdout.flush()
        time.sleep(0.5)


elements = {
    # light Purple
    26: u'┏ service discovery',
    # pale purple
    30: u'┗ automatic detection',
    # light green
    53: u'┏ monitoring',
    # pastel green
    57: u'┗ metrology',
    # couleur peau
    12: u'┏ configuraton automation',
    # jaune sombre
    8 : u'┗ system compliance',
}

what = [u'┏ service discovery', u'┗ automatic detection', u'┏ monitoring', u'┗ metrology', u'┏ configuraton automation', u'┗ system compliance']
ordered = []
for t in what:
    color = 0
    for (i, w) in elements.iteritems():
        if t == w:
            color = i
    ordered.append((t, color))

for (i, c) in enumerate(TEST_CHARS):
    cprint(u'%d : %s' % (i, c))

base_text = 'A'
for i in xrange(0, 512):
    # if i not in elements:
    #    continue
    text = elements.get(i, '%d : %s' % (i, base_text))
    lol_txt = lolcat.get_line(text, i, spread=None)
    cprint(lol_txt)

print "'''''''''''''''''''''\n\n"
for (text, color) in ordered:
    lol_txt = lolcat.get_line(text, color, spread=None)
    cprint(lol_txt)

for i in range(00, 70000):
    print "\033[74m %d " % i,
    cprint('%s' % unichr(i), color='red')
