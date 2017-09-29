import json

from opsbro.module import ConnectorModule
from opsbro.parameters import StringParameter, BoolParameter
from opsbro.gossip import gossiper
from opsbro.collectormanager import collectormgr


class ShinkenEnterpriseModule(ConnectorModule):
    implement = 'shinken-enterprise'
    
    parameters = {
        'enabled'                : BoolParameter(default=False),
        'enterprise_callback_uri': StringParameter(default=''),
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
        
        # TODO: push to shinken now :)
        f = open('/tmp/shinken-local-discovery.json', 'w')
        
        data = {
            'uuid'      : gossiper.uuid,
            'templates' : groups,
            'collectors': collectors_data,
        }
        f.write(json.dumps(data, indent=4))
        f.close()
        
        payload = {
            'uuid'     : gossiper.uuid,
            'templates': groups,
            'datas'    : {}
        }
        
        datas = payload['datas']
        
        # System info
        system_results = collectors_data.get('system', {}).get('results', {})
        
        hostname = system_results.get('hostname', '')
        payload['hostname'] = hostname
        
        fqdn = system_results.get('fqdn', '')
        if fqdn:
            datas['FQDN'] = fqdn
        
        publicip = system_results.get('publicip', '')
        if publicip:
            datas['PUBLIC_IP'] = publicip
        
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
            datas['TIMEZONE'] = timezone
        
        cpucount = system_results.get('cpucount', '')
        if cpucount:
            datas['CPU_COUNT'] = cpucount
        
        linux_distribution = system_results.get('os', {}).get('linux', {}).get('distribution', '')
        if linux_distribution:
            datas['LINUX_DISTRIBUTION'] = linux_distribution
        
        # Memory
        physical_memory = collectors_data.get('timezone', {}).get('results', {}).get('phys_total', '')
        if physical_memory:
            datas['PHYSICAL_MEMORY'] = physical_memory
        
        # Network
        network_interfaces = ','.join(collectors_data.get('interfaces', {}).get('results', {}).keys())
        if network_interfaces:
            datas['NETWORK_INTERFACES'] = network_interfaces
        
        # Geoloc (lat and long)
        geoloc = collectors_data.get('geoloc', {}).get('results', {}).get('loc', '')
        if geoloc and geoloc.count(',') == 1:
            lat, long = geoloc.split(',', 1)
            datas['LAT'] = lat
            datas['LONG'] = long
        
        # disks
        volumes = ','.join(collectors_data.get('diskusage', {}).get('results', {}).keys())
        if volumes:
            datas['VOLUMES'] = volumes
        
        print 'Payload to send', payload
