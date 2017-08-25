from opsbro.parameters import ParameterBasedType
from opsbro.log import LoggerFactory


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
