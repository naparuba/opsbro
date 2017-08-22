class Module(object):
    implement = ''
    manage_configuration_objects = []
    parameters = {}
    
    # pack name & level will be fill when we will load the klass
    pack_name = '__UNSET__'
    pack_level = '__UNSET__'
    
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
        self.daemon = None
    
    
    def get_info(self):
        return {}
    
    
    def import_configuration_object(self, object_type, o, mod_time, fname, short_name):
        raise NotImplementedError('Error: you must implement the import_configuration_object method for the module %s' % self)
    
    
    def set_daemon(self, daemon):
        self.daemon = daemon
    
    
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
