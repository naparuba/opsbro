# A ParameterBasedType will have access to the pack parameters
class ParameterBasedType(object):
    # pack name & level will be fill when we will load the klass
    pack_name = '__UNSET__'
    pack_level = '__UNSET__'
    
    # By default, no parameters are need for a collector
    # but they can declare some
    parameters = {}
    
    
    # Special parameter for managing configuration
    def __init__(self):
        self.__config = {}
        self.__configuration_error = ''
        self.__state = 'OK'  # by default all is well
    
    
    def get_config(self):
        return self.__config
    
    
    def get_parameter(self, parameter_name):
        return self.__config[parameter_name]
    
    
    def set_configuration_error(self, err):
        self.__configuration_error = err
        self.logger.error(err)
        self.__state = 'ERROR'
    
    
    def is_in_error(self):
        return self.__state == 'ERROR'
    
    
    def get_parameters_from_pack(self):
        from configurationmanager import configmgr
        pack_parameters = configmgr.get_parameters_from_pack(self.pack_name)
        
        # We prepare the config
        for (prop, property) in self.parameters.iteritems():
            # Maybe the property is not defined in the yml
            if prop not in pack_parameters:
                if property.have_default():
                    value = property.default
                else:
                    self.set_configuration_error('The for parameter %s is missing and no default value is provided' % prop)
                    continue
            else:
                value = pack_parameters[prop]
            self.logger.debug("Try to check if value %s is valid for %s" % (value, property))
            if property.is_valid(value):
                self.__config[prop] = value
                continue
            else:
                self.set_configuration_error('The value %s for parameter %s is not valid, should be of type %s' % (value, prop, property.type))
                continue
    
    
    # Someone need to know what is my conf and if it's ok
    def get_configuration_snapshot(self):
        from configurationmanager import configmgr
        pack_parameters = configmgr.get_parameters_from_pack(self.pack_name)
        
        r = {'state': self.__state, 'errors': self.__configuration_error, 'parameters': {}}
        for (prop, property) in self.parameters.iteritems():
            value = None
            is_missing = False
            is_valid = True
            is_default = False
            have_default = property.have_default()
            default_value = None
            if have_default:
                default_value = property.default
            
            if prop in pack_parameters:
                value = pack_parameters[prop]
                is_valid = property.is_valid(value)
                is_default = (value == property.default)
            else:
                is_missing = True
            entry = {'is_missing': is_missing, 'is_valid': is_valid, 'is_default': is_default, 'have_default': have_default, 'default_value': default_value, 'value': value}
            r['parameters'][prop] = entry
        return r


class NotExitingDefault:
    def __str__(self):
        return '(no default)'


class Parameter(object):
    type = 'base_parameter'
    
    
    def __init__(self, default=NotExitingDefault()):
        self.default = default
    
    
    def have_default(self):
        return not isinstance(self.default, NotExitingDefault)
    
    
    def __str__(self):
        return '[PARAMETER:: type=%s default=%s]' % (self.type, self.default)
    
    
    def as_json(self):
        r = {'type': self.type}
        if not isinstance(self.default, NotExitingDefault):
            r['default'] = self.default
        return r


class StringParameter(Parameter):
    type = 'string'
    
    
    def __init__(self, default=NotExitingDefault()):
        super(StringParameter, self).__init__(default=default)
    
    
    def is_valid(self, v):
        return isinstance(v, basestring)


class BoolParameter(Parameter):
    type = 'bool'
    
    
    def __init__(self, default=NotExitingDefault()):
        super(BoolParameter, self).__init__(default=default)
    
    
    def is_valid(self, v):
        return isinstance(v, bool)


class IntParameter(Parameter):
    type = 'int'
    
    
    def __init__(self, default=NotExitingDefault()):
        super(IntParameter, self).__init__(default=default)
    
    
    def is_valid(self, v):
        return isinstance(v, int)


class FloatParameter(Parameter):
    type = 'float'
    
    
    def __init__(self, default=NotExitingDefault()):
        super(FloatParameter, self).__init__(default=default)
    
    
    def is_valid(self, v):
        return isinstance(v, float)


class StringListParameter(Parameter):
    type = 'string_list'
    
    
    def __init__(self, default=NotExitingDefault()):
        super(StringListParameter, self).__init__(default=default)
    
    
    def is_valid(self, v):
        return isinstance(v, list)
