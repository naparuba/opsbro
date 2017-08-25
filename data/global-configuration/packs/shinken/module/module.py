import os

from opsbro.module import ConnectorModule
from opsbro.parameters import StringParameter, BoolParameter
from shinkenexporter import shinkenexporter


class ShinkenModule(ConnectorModule):
    implement = 'shinken'
    
    parameters = {
        'enabled'              : BoolParameter(default=False),
        'cfg_path'             : StringParameter(default='/etc/shinken/agent'),
        'reload_command'       : StringParameter(default='/etc/init.d/shinken reload'),
        'monitoring_tool'      : StringParameter(default='shinken'),
        'external_command_file': StringParameter(default='/var/lib/shinken/shinken.cmd'),
    }
    
    
    def __init__(self):
        ConnectorModule.__init__(self)
    
    
    def prepare(self):
        self.logger.info('SHINKEN: prepare phase')
        
        shinkenexporter.load_logger(self.logger)
        shinkenexporter.load_cfg_path(os.path.abspath(self.get_parameter('cfg_path')))
        shinkenexporter.load_reload_command(self.get_parameter('reload_command'))
        shinkenexporter.load_monitoring_tool(self.get_parameter('monitoring_tool'))
        shinkenexporter.load_external_command_file(self.get_parameter('external_command_file'))
    
    
    def launch(self):
        shinkenexporter.launch_thread()
