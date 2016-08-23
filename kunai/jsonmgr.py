import json
from util import byteify


# Class to wrap several things to json, like manage some utf8 things and such things
class JsonMgr(object):
    def __init__(self):
        pass
    
    
    def dumps(self, o):
        return json.dumps(byteify(o))
    
    
    def loads(self, s):
        return json.loads(s)


jsoner = JsonMgr()
