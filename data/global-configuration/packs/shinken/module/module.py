import os

from opsbro.log import logger
from opsbro.module import ConnectorModule
from opsbro.parameters import StringParameter, BoolParameter, IntParameter
from shinkenexporter import shinkenexporter


class ShinkenModule(ConnectorModule):
    implement = 'shinken'
    manage_configuration_objects = ['shinken']
    parameters = {
        'enabled': BoolParameter(default=False),
        'cfg_path': StringParameter(default=''),
        'reload_command': StringParameter(default=''),
        'monitoring_tool': StringParameter(default='shinken'),
        'external_command_file': StringParameter(default='/var/lib/shinken/shinken.cmd'),
    }

    
    def __init__(self):
        ConnectorModule.__init__(self)
        self.shinken = None
    
    
    def import_configuration_object(self, object_type, o, mod_time, fname, short_name):
        for prop in ['cfg_path']:
            if prop not in o:
                raise Exception('Bad shinken definition, missing property %s' % (prop))
        
        cfg_path = o['cfg_path']
        o['reload_command'] = o.get('reload_command', '')
        o['monitoring_tool'] = o.get('monitoring_tool', 'shinken')
        o['external_command_file'] = o.get('external_command_file', '/var/lib/shinken/shinken.cmd')
        # and path must be a abs path
        o['cfg_path'] = os.path.abspath(cfg_path)
        self.shinken = o
    
    
    # Prepare to open the UDP port
    def prepare(self):
        logger.info('SHINKEN: prepare phase : %s' % self.shinken)
        if self.shinken:
            shinkenexporter.load_cfg_path(self.shinken['cfg_path'])
            shinkenexporter.load_reload_command(self.shinken['reload_command'])
            shinkenexporter.load_monitoring_tool(self.shinken['monitoring_tool'])
            shinkenexporter.load_external_command_file(self.shinken['external_command_file'])
    
    def launch(self):
        shinkenexporter.launch_thread()
