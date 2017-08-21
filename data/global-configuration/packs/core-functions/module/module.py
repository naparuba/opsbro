from opsbro.module import Module

# Import modules to get core functions
import filesystem
import network
import packages
import system


class CoreFunctionsModule(Module):
    implement = 'corefunctions'
    manage_configuration_objects = []
    
    
    def __init__(self):
        Module.__init__(self)
    
    
    def get_info(self):
        return {}
