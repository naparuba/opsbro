import os
import sys
import imp
import traceback

from opsbro.log import logger
from opsbro.module import Module
from opsbro.configurationmanager import configmgr


class ModuleManager(object):
    def __init__(self):
        self.modules = []
        self.modules_directories_to_load = []
    
    
    def add_module_directory_to_load(self, dirname, pack_name, pack_level):
        self.modules_directories_to_load.append((dirname, pack_name, pack_level))
    
    
    # Raw import module source code. So they will be available in the Modules class as Class.
    def load_module_sources(self):
        modules_dirs = self.modules_directories_to_load
        
        for (dirname, pack_name, pack_level) in modules_dirs:
            # Then we load the module.py inside this directory
            mod_file = os.path.join(dirname, 'module.py')
            if not os.path.exists(mod_file):
                mod_file += 'c'  # test .pyc
            
            # if not module in it, skip it
            if not os.path.exists(mod_file):
                continue
            
            # We add this dir to sys.path so the module can load local files too
            sys.path.insert(0, dirname)
            
            # NOTE: KEEP THE ___ as they are used to let the class INSIDE te module in which pack/level they are. If you have
            # another way to give the information to the inner class inside, I take it ^^
            short_mod_name = 'module___%s___%s___%s' % (pack_level, pack_name, dirname)
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
                logger.debug('[module] %s (from pack=%s and pack level=%s) did load' % (mod, mod.pack_name, mod.pack_level))
                self.modules.append(mod)
            except Exception:
                logger.error('The module %s did fail to create: %s' % (cls, str(traceback.print_exc())))
                sys.exit(2)
    
    
    def prepare(self):
        # Now prepare them (open socket and co)
        for mod in self.modules:
            # Skip modules in error
            if mod.is_in_error():
                continue
            # If the prepare fail, exit
            try:
                mod.prepare()
            except Exception:
                logger.error('The module %s did fail to prepare: %s' % (mod, str(traceback.print_exc())))
                sys.exit(2)
    
    
    def export_http(self):
        # Now let module export their http endpoints
        for mod in self.modules:
            # Skip modules in error
            if mod.is_in_error():
                continue
            try:
                mod.export_http()
            except Exception:
                logger.error('The module %s did fail to export the HTTP API: %s' % (mod, str(traceback.print_exc())))
                sys.exit(2)
    
    
    def launch(self):
        # Launch all modules like DNS
        for mod in self.modules:
            # Don't try to launch modules in error
            if mod.is_in_error():
                continue
            try:
                mod.launch()
            except Exception:
                logger.error('Cannot launch module %s: %s' % (mod, str(traceback.print_exc())))
                sys.exit(2)
    
    
    # Now we have our modules and our parameters, link both
    def get_parameters_from_packs(self):
        for mod in self.modules:
            mod.get_parameters_from_pack()
    
    
    def get_infos(self):
        r = {}
        for mod in self.modules:
            mod_info = mod.get_info()
            r[mod.implement] = mod_info
        return r


modulemanager = ModuleManager()
