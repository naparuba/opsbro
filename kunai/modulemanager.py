import os
import sys
import imp
import traceback

from kunai.log import logger
from kunai.module import Module

myself_dir = os.path.dirname(__file__)
internal_modules_dir = os.path.join(myself_dir, 'modules')


class ModuleManager(object):
    def __init__(self):
        self.modules = []
        self.modules_configuration_types = {}
    
    
    # Raw import module source code. So they will be available in the Modules class as Class.
    def load_module_sources(self):
        modules_dirs = []
        
        # And directories
        modules_dirs.extend([os.path.join(internal_modules_dir, dirname) for dirname in os.listdir(internal_modules_dir) if os.path.isdir(os.path.join(internal_modules_dir, dirname))])
        
        for dirname in modules_dirs:
            # Then we load the module.py inside this directory
            mod_file = os.path.join(dirname, 'module.py')
            if not os.path.exists(mod_file):
                mod_file += 'c'  # test .pyc
            
            # if not module in it, skip it
            if not os.path.exists(mod_file):
                continue
            
            # We add this dir to sys.path so the module can load local files too
            sys.path.insert(0, dirname)
            
            short_mod_name = os.path.basename(dirname)
            try:
                if mod_file.endswith('.py'):
                    # important, equivalent to import fname from module.py
                    imp.load_source(short_mod_name, mod_file)
                else:
                    imp.load_compiled(short_mod_name, mod_file)
            except Exception:
                logger.error('The module %s did fail to be imported: %s' % (dirname, str(traceback.print_exc())))
                sys.exit(2)
            
            # remove the module dir from sys.path, it's not need anymore
            # NOTE: as I don't think set sys.path to a new list is a good idea (switching pointer) I prefer to use a del here
            del sys.path[:1]
        
        # Now load modules
        modules_clss = Module.get_sub_class()
        
        for cls in modules_clss:
            try:
                mod = cls()
                logger.debug('[module] %s did load' % mod)
                self.modules.append(mod)
                for configuration_type in mod.manage_configuration_objects:
                    if configuration_type not in self.modules_configuration_types:
                        logger.debug('Adding %s to manage configuration objects type %s' % (mod, configuration_type))
                        self.modules_configuration_types[configuration_type] = mod
            except Exception:
                logger.error('The module %s did fail to create: %s' % (cls, str(traceback.print_exc())))
                sys.exit(2)
    
    
    def set_daemon(self, daemon):
        for mod in self.modules:
            mod.set_daemon(daemon)
    
    
    def prepare(self):
        # Now prepare them (open socket and co)
        for mod in self.modules:
            # If the prepare fail, exit
            try:
                mod.prepare()
            except Exception:
                logger.error('The module %s did fail to prepare: %s' % (mod, str(traceback.print_exc())))
                sys.exit(2)
    
    
    def export_http(self):
        # Now prepare them (open socket and co)
        for mod in self.modules:
            # If the prepare fail, exit
            try:
                mod.export_http()
            except Exception:
                logger.error('The module %s did fail to export the HTTP API: %s' % (mod, str(traceback.print_exc())))
                sys.exit(2)
    
    
    def launch(self):
        # Launch all modules like DNS
        for mod in self.modules:
            try:
                mod.launch()
            except Exception:
                logger.error('Cannot launch module %s: %s' % (mod, str(traceback.print_exc())))
                sys.exit(2)
    
    
    def get_managed_configuration_types(self):
        return self.modules_configuration_types.keys()
    
    
    def import_managed_configuration_object(self, object_type, obj, mod_time, fname, short_name):
        logger.debug("IMPORT managed configuration object", object_type, obj, mod_time, fname, short_name)
        mod = self.modules_configuration_types[object_type]
        mod.import_configuration_object(object_type, obj, mod_time, fname, short_name)
    
    
    def get_infos(self):
        r = {}
        for mod in self.modules:
            mod_info = mod.get_info()
            r[mod.implement] = mod_info
        return r


modulemanager = ModuleManager()
