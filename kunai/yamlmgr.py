import os
import sys
import kunai.misc
from cStringIO import StringIO

p = os.path.join(os.path.dirname(kunai.misc.__file__), 'internalyaml')
sys.path.insert(0, p)

import ruamel.yaml as yaml


# Class to wrap several things to json, like manage some utf8 things and such things
class YamlMgr(object):
    def __init__(self):
        pass
    
    
    def dumps(self, o):
        f = StringIO()
        yaml.round_trip_dump(o, f, default_flow_style=False)
        buf = f.getvalue()
        return buf
    
    
    def loads(self, s):
        data = yaml.round_trip_load(s)
        return data


yamler = YamlMgr()
