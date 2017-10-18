import json
import time
from opsbro.log import cprint
pth = '/tmp/share/installation.json'

f = open(pth, 'r')
buf = f.read()
f.close()

tutorial = json.loads(buf, encoding='utf8')

print "Tutorial", tutorial.keys()


print "Will play %s (total time %.2fsec)" % (tutorial['title'], tutorial['duration'])

stdout_entries = tutorial['stdout']
for e in stdout_entries:
    wait_time = e[0]
    line = e[1]
    cprint(line, end='')
    time.sleep(wait_time)
    
print "FINISH"