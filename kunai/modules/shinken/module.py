import os

from kunai.log import logger
from kunai.module import Module
from shinkenexporter import shinkenexporter


class ShinkenModule(Module):
    implement = 'shinken'
    manage_configuration_objects = ['shinken']
    
    def __init__(self):
        Module.__init__(self)
        self.shinken = None
    
    
    def set_daemon(self, daemon):
        self.daemon = daemon
    
    
    def import_configuration_object(self, object_type, o, mod_time, fname, short_name):
        for prop in ['cfg_path']:
            if prop not in o:
                raise Exception('Bad shinken definition, missing property %s' % (prop))
        
        cfg_path = o['cfg_path']
        o['reload_command'] = o.get('reload_command', '')
        # and path must be a abs path
        o['cfg_path'] = os.path.abspath(cfg_path)
        self.shinken = o


    
    # Prepare to open the UDP port
    def prepare(self):
        logger.info('SHINKEN: prepare phase : %s' % self.daemon.shinken)
        if self.daemon.shinken:
            shinkenexporter.load_cfg_path(self.daemon.shinken['cfg_path'])
            shinkenexporter.load_reload_command(self.daemon.shinken['reload_command'])
        shinkenexporter.load_cluster(self.daemon)
    
    
    def launch(self):
        logger.error('STARTING SHINKEN MODULE')
        shinkenexporter.launch_thread()
