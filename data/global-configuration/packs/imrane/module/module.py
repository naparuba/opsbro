from __future__ import print_function
import time
import random
import traceback
import sqlite3

from opsbro.threadmgr import threader
from opsbro.module import ListenerModule
from opsbro.stop import stopper
from opsbro.httpdaemon import http_export, request
from opsbro.gossip import gossiper
from opsbro.parameters import BoolParameter, StringParameter
from opsbro.collectormanager import collectormgr
from opsbro.httpclient import get_http_exceptions, httper
from opsbro.jsonmgr import jsoner


class ImraneModule(ListenerModule):
    implement = 'imrane'
    
    parameters = {
        'enabled'        : BoolParameter(default=False),
        'collector-group': StringParameter(default='imrane-collector'),
        'agregator-group': StringParameter(default='imrane-agregator'),
        'database-path'  : StringParameter(default='/tmp/agregator.db'),
        
    }
    
    
    def __init__(self):
        ListenerModule.__init__(self)
        
        # reaping queue
        self.queue = []
        
        self.enabled = False
        
        self.database = None
        self.cursor = None
    
    
    # Prepare to open the UDP port
    def prepare(self):
        self.logger.debug('IMRANE: prepare phase')
        
        self.enabled = self.get_parameter('enabled')
        
        if self.enabled:
            self.logger.info("IMRANE: starting")
        else:
            self.logger.info('IMRANE is not enabled, skipping it')
    
    
    def get_info(self):
        state = 'STARTED' if self.enabled else 'DISABLED'
        log = ''
        return {'configuration': self.get_config(), 'state': state, 'log': log}
    
    
    def launch(self):
        threader.create_and_launch(self.launch_database_thread, name='Database thread', essential=True, part='imrane')
        threader.create_and_launch(self.launch_collector_thread, name='Collector thread', essential=True, part='imrane')
    
    
    def _import_data(self, data):
        results = data['results']
        from_name = data['from']
        self.queue.append((from_name, results))
    
    
    def stopping_agent(self):
        if self.database:
            self.logger.info('Closing database')
            self.database.commit()
            self.database.close()
    
    
    # Same but for the TCP connections
    # TODO: use a real daemon part for this, this is not ok for fast receive
    def launch_database_thread(self):
        while not stopper.interrupted:
            agregator_group = self.get_parameter('agregator-group')
            database_enabled = gossiper.is_in_group(agregator_group)
            
            if not database_enabled:
                self.logger.debug('IMRANE: not a database thread')
                time.sleep(1)
                continue
            
            if self.database is None:
                database_path = self.get_parameter('database-path')
                self.database = sqlite3.connect(database_path)
                
                self.cursor = self.database.cursor()
                # Create data
                # TODO: check if not already exists
                tb_exists = "SELECT name FROM sqlite_master WHERE type='table' AND name='Data'"
                if not self.cursor.execute(tb_exists).fetchone():
                    self.cursor.execute("CREATE TABLE Data(id INTEGER PRIMARY KEY, Epoch INTEGER, HostName TEXT, KeyName TEXT, Value TEXT)")
            
            self.logger.info('IMRANE: database loop')
            self.logger.info('IMRANE: manage: %s' % self.queue)
            
            # Switch to avoid locking
            queue = self.queue
            self.queue = []
            
            now = int(time.time())
            for (from_name, results) in queue:
                self.logger.info('SAVING INTO DATABASE: %s => %s' % (from_name, results))
                # TODO: database code
                for (key, value) in results.items():
                    q = '''INSERT INTO Data(Epoch, HostName, KeyName, Value) VALUES (%s,'%s','%s','%s')''' % (now, from_name, key, value)
                    self.logger.info('EXECUTING: %s' % q)
                    self.cursor.execute(q)
            self.database.commit()
            
            time.sleep(1)
    
    
    # Same but for the TCP connections
    # TODO: use a real daemon part for this, this is not ok for fast receive
    def launch_collector_thread(self):
        last_collector_check = 0
        while not stopper.interrupted:
            collector_group = self.get_parameter('collector-group')
            collector_enabled = gossiper.is_in_group(collector_group)
            
            if not collector_enabled:
                self.logger.debug('IMRANE: not a collector thread')
                time.sleep(1)
                continue
            self.logger.info('IMRANE: collector loop')
            self.logger.info('IMRANE: manage: %s' % self.queue)
            imrane_collector = None
            for collector in collectormgr.collectors.values():
                name = collector['name']
                if name == 'imrane':
                    imrane_collector = collector
                    break
            if imrane_collector is None:
                self.logger.error('IMRANE: cannot find the imrane collector, skiping this loop')
                time.sleep(1)
                continue
            
            # Maybe this collector did not run since we last look at it, if so, skip it
            last_check = imrane_collector['last_check']
            if last_check == last_collector_check:
                self.logger.info('IMRANE: the collector did not run since the last loop, skiping this turn')
                time.sleep(1)
                continue
            last_collector_check = last_check
            
            results = imrane_collector['results']
            self.logger.info('IMRANE: collector result: %s' % results)
            
            our_node = gossiper.get(gossiper.uuid)
            our_node_name = our_node['name']
            
            agregator_group = self.get_parameter('agregator-group')
            agregator_nodes = gossiper.find_group_nodes(agregator_group)
            if len(agregator_nodes) == 0:
                self.logger.error('IMRANE ERROR: there are no agregator nodes, skiping data sending')
                time.sleep(1)
                continue
            
            agregator_node_uuid = random.choice(agregator_nodes)
            agregator_node = gossiper.get(agregator_node_uuid)
            if agregator_node is None:  # oups: thread race bug
                time.sleep(1)
                continue
            
            address = agregator_node['addr']
            port = agregator_node['port']
            display_name = agregator_node['display_name']
            self.logger.info('IMRANE: did choose %s (%s:%s) for sending' % (display_name, address, port))
            
            uri = 'http://%s:%s/imrane' % (address, port)
            try:
                r = httper.post(uri, params={'results': results, 'from': our_node_name}, headers={'Content-Type': 'application/json;charset=UTF-8'})
                self.logger.debug("Result insert", r)
            except get_http_exceptions() as exp:
                self.logger.error('Cannot connect to agregator: %s' % exp)
            
            # always sleep to not hammer the CPU
            time.sleep(1)
    
    
    # Export end points to get/list TimeSeries
    def export_http(self):
        @http_export('/imrane', method='POST')
        @http_export('/imrane/', method='POST')
        def get_ts_values():
            self.logger.info('CALLING /imrane POST')
            try:
                data_raw = request.body.getvalue()
                self.logger.info('POST: get body value: %s' % data_raw)
                data = jsoner.loads(data_raw)
                self.logger.info('POST: get results: %s' % data)
                self._import_data(data)
            except:
                self.logger.error('IMRANE: ERROR %s' % traceback.format_exc())
            return None
