from opsbro.parameters import ParameterBasedType
from opsbro.log import LoggerFactory
from opsbro.packer import packer


class Module(ParameterBasedType):
    implement = ''
    
    class __metaclass__(type):
        __inheritors__ = set()
        
        
        def __new__(meta, name, bases, dct):
            klass = type.__new__(meta, name, bases, dct)
            # This class need to implement a real role to be load
            if klass.implement:
                # When creating the class, we need to look at the module where it is. It will be create like this (in modulemanager)
                # module___global___windows___collector_iis ==> level=global  pack_name=windows, collector_name=collector_iis
                from_module = dct['__module__']
                elts = from_module.split('___')
                # Let the klass know it
                klass.pack_level = elts[1]
                klass.pack_name = elts[2]
                meta.__inheritors__.add(klass)
            return klass
    
    @classmethod
    def get_sub_class(cls):
        return cls.__inheritors__
    
    
    def __init__(self):
        ParameterBasedType.__init__(self)
        
        self.daemon = None
        # Global logger for this part
        self.logger = LoggerFactory.create_logger('module.%s' % self.__class__.pack_name)
        
        if hasattr(self, 'pack_level') and hasattr(self, 'pack_name'):
            self.pack_directory = packer.get_pack_directory(self.pack_level, self.pack_name)
        else:
            self.pack_directory = ''
    
    
    def get_info(self):
        return {}
    
    
    def prepare(self):
        return
    
    
    def launch(self):
        return
    
    
    def export_http(self):
        return


class FunctionsExportModule(Module):
    module_type = 'functions_export'


class ConnectorModule(Module):
    module_type = 'connector'


class ListenerModule(Module):
    module_type = 'listener'


class HandlerModule(Module):
    module_type = 'handler'
    
    
    def __init__(self):
        super(HandlerModule, self).__init__()
        from opsbro.handlermgr import handlermgr
        implement = self.implement
        if not implement:
            self.logger.error('Unknown implement type for module, cannot load it.')
            return
        handlermgr.register_handler_module(implement, self)
