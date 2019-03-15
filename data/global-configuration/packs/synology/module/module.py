from __future__ import print_function
import time

from opsbro.threadmgr import threader
from opsbro.module import ListenerModule
from opsbro.stop import stopper
from opsbro.collectormanager import collectormgr

from opsbro.gossip import gossiper
from opsbro.httpclient import get_http_exceptions, httper
from opsbro.parameters import BoolParameter, StringParameter


class SynologyModule(ListenerModule):
    implement = 'synology'
    
    parameters = {
        'enabled'         : BoolParameter(default=False),
        'export_uri'      : StringParameter(default='http://92.222.35.193:8080/synology'),
        'customer_key'    : StringParameter(default=''),
        'inventory_number': StringParameter(default=''),
    }
    
    
    def __init__(self):
        ListenerModule.__init__(self)
        
        # Graphite reaping queue
        self.graphite_queue = []
        
        self.enabled = False
        self.export_uri = ''
        self.customer_key = ''
        self.inventory_number = ''
    
    
    # Prepare to open the UDP port
    def prepare(self):
        self.logger.debug('Synology: prepare phase')
        
        self.enabled = self.get_parameter('enabled')
        self.export_uri = self.get_parameter('export_uri')
    
    
    def get_info(self):
        state = 'STARTED' if self.enabled else 'DISABLED'
        log = ''
        return {'configuration': self.get_config(), 'state': state, 'log': log}
    
    
    def launch(self):
        threader.create_and_launch(self.launch_main, name='Synology', essential=True, part='synology')
    
    
    # Thread for listening to the graphite port in UDP (2003)
    def launch_main(self):
        while not stopper.is_stop():
            self.enabled = self.get_parameter('enabled')
            if not self.enabled:
                time.sleep(1)
                continue
            self.export_uri = self.get_parameter('export_uri')
            self.customer_key = self.get_parameter('customer_key')
            self.inventory_number = self.get_parameter('inventory_number')
            if not self.customer_key:
                self.warning('You must have a customer key')
                time.sleep(1)
                continue
            
            syno_collector = collectormgr.collectors.get('synology', None)
            if syno_collector is None:
                self.logger.error('The synology collector is missing')
                time.sleep(1)
                continue
            
            results = syno_collector.get('results', None)
            if results is None:
                self.logger.warning('The synology collector did not run')
                time.sleep(1)
                continue
            
            try:
                r = httper.post(self.export_uri, params={'uuid'            : gossiper.uuid,
                                                         'customer_key'    : self.customer_key,
                                                         'inventory_number': self.inventory_number,
                                                         'results'         : results}, headers={})
                self.logger.debug("Result insert", r)
            except get_http_exceptions() as exp:
                self.logger.error('Cannot connect to export uri datasources: %s' % exp)
            time.sleep(1)
