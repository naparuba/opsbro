import os
import sys
import imp
import traceback

from kunai.log import logger

myself_dir = os.path.dirname(__file__)
internal_modules_dir = os.path.join(myself_dir, 'modules')


class ModuleManager(object):
    def __init__(self):
        self.modules = []
    
    # Raw import module source code. So they will be available in the Modules class as Class.
    # TODO: manage also module instanciation
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
            

modulemanager = ModuleManager()
