from kunai.log import logger
from kunai.now import NOW

class Module(object):
    class __metaclass__(type):
        __inheritors__ = set()
        
        
        def __new__(meta, name, bases, dct):
            klass = type.__new__(meta, name, bases, dct)
            meta.__inheritors__.add(klass)
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
    
    