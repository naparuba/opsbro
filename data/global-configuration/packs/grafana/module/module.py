import os
import json
import time

try:
    import requests as rq
except ImportError:
    rq = None

from opsbro.module import ConnectorModule
from opsbro.parameters import StringParameter, BoolParameter
from opsbro.gossip import gossiper
from opsbro.pubsub import pubsub
from opsbro.threadmgr import threader
from opsbro.stop import stopper
from opsbro.detectormgr import detecter
from opsbro.gossip import gossiper
from opsbro.kv import kvmgr
from opsbro.httpclient import HTTP_EXCEPTIONS


class GrafanaModule(ConnectorModule):
    implement = 'grafana'
    
    parameters = {
        'enabled': BoolParameter(default=False),
        'uri'    : StringParameter(default='http://localhost:3000'),
        'api_key': StringParameter(default=''),
    }
    
    
    def __init__(self):
        ConnectorModule.__init__(self)
        self.enabled = False
        self.uri = 'http://localhost:3000'
        self.api_key = ''
        self.node_changes = []
    
    
    def prepare(self):
        self.logger.info('Grafana: prepare phase')
        self.enabled = self.get_parameter('enabled')
        self.uri = self.get_parameter('uri')
        self.api_key = self.get_parameter('api_key')
        
        if not self.enabled:
            self.logger.debug('Grafana: export module is not enabled')
            return
        
        if rq is None:
            self.logger.error('Missing the python-requests librairy, please install it')
            self.enabled = False
            return
            # register to node events
            # pubsub.sub('new-node', self.new_node_callback)
            # pubsub.sub('delete-node', self.delete_node_callback)
    
    
    # def new_node_callback(self, node_uuid=None):
    #    self.node_changes.append(('new-node', node_uuid))
    
    
    # def delete_node_callback(self, node_uuid=None):
    #    self.node_changes.append(('delete-node', node_uuid))
    
    def __get_headers(self):
        return {'Content-Type': 'application/json;charset=UTF-8', 'Authorization': 'Bearer %s' % self.api_key}
    
    
    def insert_node_into_grafana(self, nuuid):
        node = gossiper.get(nuuid)
        if node is None:
            return
        name = node['name']
        addr = node['addr']
        port = node['port']
        data_source_name = "%s--opsbro--%s" % (name, nuuid)
        entry = {"name": data_source_name, "type": "graphite", "url": "http://%s:%d" % (addr, port), "access": "proxy"}
        uri = '%s/api/datasources' % (self.uri)
        try:
            r = rq.post(uri, data=json.dumps(entry), headers=self.__get_headers())
            self.logger.debug("Result insert", r.text)
        except HTTP_EXCEPTIONS, exp:
            self.logger.error('Cannot connect to grafana datasources: %s' % exp)
            return
    
    
    def remove_data_source(self, data_source_id):
        self.logger.info('Cleaning data source %d from grafana because the node is no more' % data_source_id)
        uri = '%s/api/datasources/%d' % (self.uri, data_source_id)
        try:
            r = rq.delete(uri, headers=self.__get_headers())
            self.logger.debug("Result delete", r.text)
        except HTTP_EXCEPTIONS, exp:
            self.logger.error('Cannot connect to grafana datasources: %s' % exp)
            return
    
    
    def get_data_sources_from_grafana(self):
        uri = '%s/api/datasources' % (self.uri)
        our_data_sources = {}
        try:
            r = rq.get(uri, headers=self.__get_headers())
            try:
                all_data_sources = json.loads(r.text)
            except (ValueError, TypeError), exp:
                self.logger.error('Cannot load json from grafana datasources: %s' % exp)
                return None
        except HTTP_EXCEPTIONS, exp:
            self.logger.error('Cannot connect to grafana datasources: %s' % exp)
            return None
        self.logger.debug("All data sources")
        self.logger.debug(str(all_data_sources))
        # Error message is a dict with jsut a key: message
        if isinstance(all_data_sources, dict):
            error_message = all_data_sources.get('message', '')
            if error_message:
                if error_message == 'Unauthorized':
                    self.logger.error('Your API key is not autorized to list data sources.')
                    return None
                self.logger.error('Unknown error from grafana API: %s' % error_message)
                return None
        
        # A data source will look like this:
        # [{u'name'    : u'SuperBla',
        ##  u'database': u'',
        # u'url': u'http://super:6768',
        #  u'basicAuth': False,
        # u'jsonData': {},
        # u'access': u'proxy',
        # u'typeLogoUrl': u'public/app/plugins/datasource/graphite/img/graphite_logo.png',
        # u'orgId': 1,
        # u'user': u'',
        #  u'password': u'',
        # u'type': u'graphite',
        #  u'id': 1,
        # u'isDefault': False}]
        for data_source in all_data_sources:
            if data_source.get('type', '') != 'graphite':
                continue
            src_name = data_source.get('name', '')
            if '--opsbro--' in src_name:
                elts = src_name.split('--opsbro--')
                if len(elts) == 2:
                    nuuid = elts[1]
                    our_data_sources[nuuid] = data_source
        return our_data_sources
    
    
    def launch(self):
        threader.create_and_launch(self.do_launch, name='Grafana module data sources synchronizer', essential=True, part='grafana')
    
    
    def do_launch(self):
        while not stopper.interrupted:
            self.logger.debug('Grafana loop')
            
            if not self.enabled:
                continue
            
            nodes_in_grafana = self.get_data_sources_from_grafana()
            # If we have an issue to grafana, skip this loop
            if nodes_in_grafana is None:
                time.sleep(1)
                continue
            nodes_in_grafana_set = set(nodes_in_grafana.keys())
            with gossiper.nodes_lock:
                gossip_nodes_uuids = gossiper.nodes.keys()
            gossip_nodes_uuids = set(gossip_nodes_uuids)
            
            self.logger.debug("Nodes in grafana", nodes_in_grafana_set)
            self.logger.debug("Nodes in gossip", gossip_nodes_uuids)
            nodes_that_must_be_clean = nodes_in_grafana_set - gossip_nodes_uuids
            nodes_to_insert = gossip_nodes_uuids - nodes_in_grafana_set
            self.logger.debug("Nodes that must be clean", nodes_that_must_be_clean)
            self.logger.debug("Nodes to insert into grafana", nodes_to_insert)
            for nuuid in nodes_to_insert:
                self.logger.debug("Nodes", nuuid, "must be inserted into grafana")
                self.insert_node_into_grafana(nuuid)
            
            for nuuid in nodes_that_must_be_clean:
                node_data_source_id = nodes_in_grafana[nuuid]['id']
                self.logger.debug("Node ", nuuid, "is no more need in grafana. Removing its data source")
                self.remove_data_source(node_data_source_id)
            
            time.sleep(1)
