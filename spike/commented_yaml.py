

'''
from __future__ import print_function

import sys
import ruamel.yaml
from ruamel.yaml.comments import CommentedMap


class MyObj():
    name = "boby"
    age = 34

    def convert_to_yaml_struct(self):
        x = CommentedMap()
        a = CommentedMap()
        x[data.name] = a
        x.yaml_add_eol_comment('this is the name', 'boby', 11)
        a['age'] = data.age
        a.yaml_add_eol_comment('in years', 'age', 11)
        return x

    @staticmethod
    def yaml_representer(dumper, data, flow_style=False):
        assert isinstance(dumper, ruamel.yaml.RoundTripDumper)
        return dumper.represent_dict(data.convert_to_yaml_struct())


ruamel.yaml.RoundTripDumper.add_representer(MyObj, MyObj.yaml_representer)

ruamel.yaml.round_trip_dump(MyObj(), sys.stdout)
'''

import os
import sys
import opsbro.misc

p = os.path.join(os.path.dirname(opsbro.misc.__file__), 'internalyaml')
print p
sys.path.insert(0, p)

import ruamel.yaml

# from opsbro.misc.internalyaml.ruamel import yaml


s = '''
# Pre comment
# on two lines
- super string # is this a valid comment
- k1: blabla
  k2: 36.000
  k3:
      # is this a valid comment
      - sub 1
      - sub 2
# ending comment
'''


s = '''
# Document gull comment
# document full comment bis
key1: blabla  # key1 comment
key2: 36.000
key3:  # key3 level comment
  # K3 sub list comment
  - entry key3.1  #key3.entry1 comment
  - sub 2
# ending comment
# ending comment bis
'''

print dir(ruamel.yaml)
#data = ruamel.yaml.round_trip_load_all(s)
data = ruamel.yaml.load(s, ruamel.yaml.RoundTripLoader)

print "DATA", data, type(data), dir(data)
print 'DICT', data.__dict__
print data._yaml_format.__dict__
print data._yaml_line_col.__dict__

print "CA", data.ca
print "CA internals", data.ca.__dict__
print "CA dir", dir(data.ca)
print "CA.attrib", data.ca.attrib
print "CA comment", data.ca.comment

print "CA items", data.ca.items

print "\n\n"
print "VIEW", data.viewitems()

assert (data[0] == 'super string')
assert (data[1]['k1'] == 'blabla')
assert (data[1]['k2'] == 36.00)

out = '/tmp/out.yaml'
with open(out, 'w') as fp:
    ruamel.yaml.round_trip_dump(data, fp, default_flow_style=False)

with open(out, 'r') as fp:
    buf = fp.read()
    print buf
