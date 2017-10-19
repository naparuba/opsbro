
import json
import os
import time
from opsbro.log import cprint
from opsbro.info import BANNER, TITLE_COLOR
import sys

pth = os.path.join(os.path.dirname(__file__), 'linux-dashboard.json')

f = open(pth, 'r')
buf = f.read()
f.close()

tutorial = json.loads(buf, encoding='utf8')


cprint('Playing %s dashboard sample (preview)' % TITLE_COLOR)
time.sleep(1)

clean = '\033c'
first_clean_read = False

stdout_entries = tutorial['stdout']
for e in stdout_entries:
    wait_time = e[0]
    line = e[1]
    if clean in line:
        if first_clean_read:
            time.sleep(1)
        first_clean_read = True
        wait_time = 0.01
    cprint(line, end='')
    sys.stdout.flush()
    time.sleep(wait_time)
    
cprint('\n\n\n')

cprint(BANNER)
cprint('You did enjoy a preview of OpsBro dashboard, here for the linux system. More to see at ', end='')
cprint('https://github.com/naparuba/opsbro/', color='magenta')
cprint('And if you want a freaking good and powerful monitoring tool for large corps, look at ', end='')
cprint('Shinken framework & Shinken Enterprise', color='magenta', end='')
cprint(' the main projects of Shinken Solutions team at ', end='')
cprint('https://www.shinken-enterprise.com', color='magenta')

cprint('\n')
time.sleep(5)
