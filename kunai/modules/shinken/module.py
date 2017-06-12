from kunai.log import logger
from kunai.module import Module
from shinkenexporter import shinkenexporter


class ShinkenModule(Module):
    implement = 'shinken'
    
    
    def __init__(self, daemon):
        Module.__init__(self, daemon)
    
    
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
