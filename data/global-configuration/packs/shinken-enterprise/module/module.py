import json

from opsbro.module import ConnectorModule
from opsbro.parameters import StringParameter, BoolParameter
from opsbro.gossip import gossiper
from opsbro.collectormanager import collectormgr


class ShinkenEnterpriseModule(ConnectorModule):
    implement = 'shinken-enterprise'
    
    parameters = {
        'enabled'    : BoolParameter(default=False),
        'file_result': StringParameter(default=''),
    }
    
    
    # We only work at the stopping phase, when all is finish, to get back our discovery
    def stopping_agent(self):
        enabled = self.get_parameter('enabled')
        if not enabled:
            return
        with gossiper.groups_lock:
            groups = gossiper.groups[:]
        self.logger.info('Pushing back ours groups and discovery informations to Shinken Enterprise')
        
        collectors_data = {}
        for (ccls, e) in collectormgr.collectors.iteritems():
            cname, c = collectormgr.get_collector_json_extract(e)
            collectors_data[cname] = c
            
        # In groups=> templates, we do not want : and . in the names
        _mapping = {':': '--', '.': '--'}
        use_value = ','.join(groups)
        for (k, v) in _mapping.iteritems():
            use_value = use_value.replace(k, v)

        payload = {
            '_AGENT_UUID': gossiper.uuid,
            'use'        : use_value,
        }
        
        # System info
        system_results = collectors_data.get('system', {}).get('results', {})
        
        hostname = system_results.get('hostname', '')
        payload['host_name'] = hostname
        
        fqdn = system_results.get('fqdn', '')
        if fqdn:
            payload['_FQDN'] = fqdn
        
        publicip = system_results.get('publicip', '')
        if publicip:
            payload['_PUBLIC_IP'] = publicip
        
        # which address to use in fact?
        # how to choose:   fqdn > public_ip > hostname
        if fqdn:
            payload['address'] = fqdn
        elif publicip:
            payload['address'] = publicip
        else:
            payload['address'] = hostname
        
        # Timezone
        timezone = collectors_data.get('timezone', {}).get('results', {}).get('timezone', '')
        if timezone:
            payload['_TIMEZONE'] = timezone.decode('utf8', 'ignore')
        
        cpucount = system_results.get('cpucount', '')
        if cpucount:
            payload['_CPU_COUNT'] = str(cpucount)  # data must be string
        
        linux_distribution = system_results.get('os', {}).get('linux', {}).get('distribution', '')
        if linux_distribution:
            payload['_LINUX_DISTRIBUTION'] = linux_distribution
        
        # Memory
        physical_memory = collectors_data.get('timezone', {}).get('results', {}).get('phys_total', '')
        if physical_memory:
            payload['_PHYSICAL_MEMORY'] = physical_memory
        
        # Network
        try:
            network_interfaces = ','.join(collectors_data.get('interfaces', {}).get('results', {}).keys())
        except AttributeError:  # was without interfaces
            network_interfaces = ''
        if network_interfaces:
            payload['_NETWORK_INTERFACES'] = network_interfaces
        
        # Geoloc (lat and long)
        try:
            geoloc = collectors_data.get('geoloc', {}).get('results', {}).get('loc', '')
        except AttributeError:  # was without interfaces
            geoloc = ''
        if geoloc and geoloc.count(',') == 1:
            lat, long = geoloc.split(',', 1)
            payload['_LAT'] = lat
            payload['_LONG'] = long
        
        # disks
        try:
            volumes = ','.join(collectors_data.get('diskusage', {}).get('results', {}).keys())
        except AttributeError:
            volumes = ''
        if volumes:
            payload['_VOLUMES'] = volumes
        
        file_result = self.get_parameter('file_result')
        if file_result:
            f = open(file_result, 'w')
            f.write(json.dumps(payload, indent=4))
            f.close()
            
            
            
        # try:
        #    self.logger.info('Sending back discovery data to shinken at %s' % enterprise_callback_uri)
        #    conn = httplib.HTTPConnection(enterprise_callback_uri)
        #    conn.set_debuglevel(1)
        
        #    params = json.dumps({'host': payload})
        #    headers = {'User-agent': 'agent', 'Accept': 'application/json'}
        #    conn.request('PUT', '/v1/hosts/', params, headers)
        
        #    response = conn.getresponse()
        #    print response.status, response.reason
        #    conn.close()
        # except Exception as exp:
        #    self.logger.error('Cannot send back discovery data to shinken: %s' % exp)
