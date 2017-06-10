from kunai.log import logger
from kunai.now import NOW

class Module(object):
    implement = ''
    class __metaclass__(type):
        __inheritors__ = set()
        
        
        def __new__(meta, name, bases, dct):
            klass = type.__new__(meta, name, bases, dct)
            # This class need to implement a real role to be load
            if klass.implement:
                meta.__inheritors__.add( klass )
            return klass
    
    @classmethod
    def get_sub_class(cls):
        return cls.__inheritors__
    
    def __init__(self, daemon):
        self.daemon = daemon
        
        
    def prepare(self):
        return
    
    
    def launch(self):
        return
    
    
    def export_http(self):
        return