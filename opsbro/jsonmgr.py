import json
from .util import byteify, string_decode


# Class to wrap several things to json, like manage some utf8 things and such things
class JsonMgr(object):
    def __init__(self):
        pass
    
    
    def dumps(self, o):
        return json.dumps(byteify(o))
    
    
    def loads(self, s, encoding='utf8'):
        s = string_decode(s)
        try:
            r = json.loads(s, encoding='utf8')
        except Exception as exp:  # beware: ValueError in python2, but some freaking exception in python3
            raise ValueError(str(exp))
        return r


jsoner = JsonMgr()
