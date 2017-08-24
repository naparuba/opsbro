from opsbro.log import LoggerFactory


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
        self.__module_config = {}
        # Global logger for this part
        self.logger = LoggerFactory.create_logger('module.%s' % self.__class__.pack_name)
        self.__configuration_error = ''
        self.__state = 'OK'  # by default all is well
    
    
    def get_info(self):
        return {}
    
    
    def get_config(self):
        return self.__module_config
    
    
    def prepare(self):
        return
    
    
    def launch(self):
        return
    
    
    def export_http(self):
        return
    
    
    def get_parameter(self, parameter_name):
        return self.__module_config[parameter_name]
    
    
    def set_configuration_error(self, err):
        self.__configuration_error = err
        self.logger.error(err)
        self.__state = 'ERROR'
    
    
    def is_in_error(self):
        return self.__state == 'ERROR'
    
    
    def get_parameters_from_pack(self):
        from configurationmanager import configmgr
        pack_parameters = configmgr.get_module_parameters_from_pack(self.pack_name)
        
        pack_parameters_keys = set(pack_parameters.keys())
        module_parameters_keys = set(self.parameters.keys())
        
        # The keys in the yml should match exactly the module definition one
        missing_parameters = module_parameters_keys - pack_parameters_keys
        if missing_parameters:
            self.set_configuration_error('The parameters: %s are missing in the module definition. You must defined them.' % (','.join(list(missing_parameters))))
            return
        
        too_much_parameters = pack_parameters_keys - module_parameters_keys
        if too_much_parameters:
            self.set_configuration_error('The parameters: %s are set in the module definition but they are unknown for this module. You must remove them or check if it is not a typo.' % (','.join(list(too_much_parameters))))
            return
        
        # We prepare the config
        for (prop, property) in self.parameters.iteritems():
            value = pack_parameters[prop]
            self.logger.debug("Try to check if value %s is valid for %s" % (value, property))
            if property.is_valid(value):
                self.__module_config[prop] = value
                continue
            else:
                self.set_configuration_error('The value %s for parameter %s is not valid, should be of type %s' % (value, prop, property.type))
                continue


class FunctionsExportModule(Module):
    module_type = 'functions_export'


class ConnectorModule(Module):
    module_type = 'connector'


class ListenerModule(Module):
    module_type = 'listener'
