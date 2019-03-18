from __future__ import print_function
import time
import base64

from opsbro.threadmgr import threader
from opsbro.module import ListenerModule
from opsbro.stop import stopper
from opsbro.collectormanager import collectormgr

from opsbro.gossip import gossiper
from opsbro.httpclient import get_http_exceptions, httper
from opsbro.parameters import BoolParameter, StringParameter
from opsbro.jsonmgr import jsoner


class SQPModule(ListenerModule):
    implement = 'sqp'
    
    parameters = {
        'enabled'          : BoolParameter(default=False),
        'export_uri'       : StringParameter(default='http://92.222.35.193:8080/sqp'),
        'customer_key'     : StringParameter(default=''),
        'inventory_number' : StringParameter(default=''),
        
        'listener_uri'     : StringParameter(default='http://192.168.1.73:7761/shinken/listener-rest/v1/hosts'),
        'listener_login'   : StringParameter(default='root'),
        'listener_password': StringParameter(default='root'),
    }
    
    
    def __init__(self):
        ListenerModule.__init__(self)
        
        # Graphite reaping queue
        self.graphite_queue = []
        
        self.enabled = False
        self.export_uri = ''
        self.customer_key = ''
        self.inventory_number = ''
        
        self.listener_uri = ''
        self.listener_login = ''
        self.listener_password = ''
        
        self.is_registered = False
        self.current_groups = set()
    
    
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
    
    
    # The element was not registered to the SaaS, do it
    def register(self):
        try:
            self.listener_uri = self.get_parameter('listener_uri')
            self.listener_login = self.get_parameter('listener_login')
            self.listener_password = self.get_parameter('listener_password')
            headers = {}
            if self.listener_login:
                b64auth = base64.standard_b64encode("%s:%s" % (self.listener_login, self.listener_password))
                headers["Authorization"] = "Basic %s" % b64auth
            # Too early
            if len(gossiper.groups) == 0:
                return
            self.current_groups = set(gossiper.groups)  # copy it
            use_strings = 'sqp,toto,%s' % (','.join(self.current_groups)).replace(':', '-')
            
            # New element
            if not self.is_registered:
                r = httper.put(self.listener_uri, data=jsoner.dumps({'host_name'   : gossiper.uuid,
                                                                     'display_name': gossiper.name,
                                                                     'use'         : use_strings}), headers=headers)
            # Modification: how to detect and fix?
            # TODO: is not accepted from listener
            else:
                r = httper.post(self.listener_uri, params={'host_name'   : gossiper.uuid,
                                                           'display_name': gossiper.name,
                                                           'use'         : use_strings}, headers=headers)
            self.logger.debug("Result put new host", r)
            self.is_registered = True
        except get_http_exceptions() as exp:
            self.logger.error('Cannot connect to listener: %s' % exp)
    
    
    # Thread for listening to the graphite port in UDP (2003)
    def launch_main(self):
        while not stopper.is_stop():
            self.enabled = self.get_parameter('enabled')
            if not self.enabled:
                time.sleep(1)
                continue
            
            if not self.is_registered:
                self.register()
            
            # Maybe it's because the gossip groups did changed
            if self.current_groups != set(gossiper.groups):
                self.register()
            
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
            
            # send raw data to the data handler
            try:
                r = httper.post(self.export_uri, params={'uuid'            : gossiper.uuid,
                                                         'customer_key'    : self.customer_key,
                                                         'inventory_number': self.inventory_number,
                                                         'results'         : results}, headers={})
                self.logger.debug("Result insert", r)
            except get_http_exceptions() as exp:
                self.logger.warning('Cannot connect to export uri datasources: %s' % exp)
            time.sleep(1)
