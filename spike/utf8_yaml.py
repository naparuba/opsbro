# -*- coding: utf-8 -*-



import os
import sys
import opsbro.misc
from opsbro.log import cprint

p = os.path.join(os.path.dirname(opsbro.misc.__file__), 'internalyaml')
print(p)
sys.path.insert(0, p)

import ruamel.yaml

from opsbro.misc.internalyaml.ruamel import yaml


s = u'''
# Pre comment
# on two lines
- "⌐■_■"
- "⌐■_■"
# ending comment
'''
#sys.argv = map(lambda arg: arg.decode(sys.stdout.encoding), sys.argv)

for arg in [os.fsencode(arg) for arg in sys.argv]:
    v = arg.decode("utf-8")
    cprint(v)
#    print(v)


print(type(s))
#data = ruamel.yaml.round_trip_load_all(s)
data = ruamel.yaml.load(s, ruamel.yaml.RoundTripLoader)

cprint(u'%s' % data)
print('DICT', data.__dict__)
print(data._yaml_format.__dict__)
print(data._yaml_line_col.__dict__)

print("CA", data.ca)
print("CA internals", data.ca.__dict__)
print("CA dir", dir(data.ca))
print("CA.attrib", data.ca.attrib)
print("CA comment", data.ca.comment)

print("CA items", data.ca.items)

print("\n\n")
print("VIEW", data.viewitems())

assert (data[0] == 'super string')
assert (data[1]['k1'] == 'blabla')
assert (data[1]['k2'] == 36.00)

out = '/tmp/out.yaml'
with open(out, 'w') as fp:
    ruamel.yaml.round_trip_dump(data, fp, default_flow_style=False)

with open(out, 'r') as fp:
    buf = fp.read()
    print(buf)
