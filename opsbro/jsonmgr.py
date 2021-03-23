# cjson is best for write
import json as json_write

json_read_lib = ''
# simplejson > json
try:
    import simplejson as json_read
    
    json_read_lib = 'simplejson'
except ImportError:
    import json as json_read  # always exists
    
    json_read_lib = 'cjson'

from .util import byteify, string_decode


# (1000 objets de 10K)
#
# json: Write:0.297  <==BEST
# json: Read:0.728
# simplejson: Write:0.369
# simplejson: Read:0.214 <==OK

# Class to wrap several things to json, like manage some utf8 things and such things
class JsonMgr(object):
    def __init__(self):
        self.json_read_lib = json_read_lib
    
    
    def dumps(self, o, indent=None):
        return json_write.dumps(byteify(o), indent=indent)
    
    
    def loads(self, s, encoding='utf8'):
        s = string_decode(s)
        try:
            try:
                r = json_read.loads(s, encoding=encoding)
            except TypeError:  #old fedora, do not know about encoding
                r = json_read.loads(s)
        except Exception as exp:  # beware: ValueError in python2, but some freaking exception in python3
            raise ValueError(str(exp))
        return r


jsoner = JsonMgr()
