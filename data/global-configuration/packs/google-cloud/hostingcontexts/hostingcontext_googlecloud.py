import os
import json

from opsbro.httpclient import get_http_exceptions, httper
from opsbro.hostingcontextmanager import InterfaceHostingContext


class GoogleCloudHostingContext(InterfaceHostingContext):
    name = 'google-cloud'
    
    
    def __init__(self):
        super(GoogleCloudHostingContext, self).__init__()
        self.__meta_data = None
    
    
    # We are in an Azure host if we have the /sys/class/dmi/id/board_vendor with 'Microsoft Corporation'
    def is_active(self):
        if os.path.exists('/sys/class/dmi/id/board_vendor'):
            with open('/sys/class/dmi/id/board_vendor') as f:
                buf = f.read().strip()
                if buf == 'Google':
                    return True
        return False
    
    
    # {
    #    "instance": {
    #        "attributes": {},
    #        "cpuPlatform": "Intel Ivy Bridge",
    #        "description": "",
    #        ...
    #        "hostname": "ubuntu-xenial-1.c.api-project-337367557486.internal",
    #        "id": 5992226485404826147,
    #        "image": "projects/ubuntu-os-cloud/global/images/ubuntu-1604-xenial-v20180214",
    #        ...
    #        "machineType": "projects/337367557486/machineTypes/f1-micro",
    #        "maintenanceEvent": "NONE",
    #        "name": "ubuntu-xenial-1",
    #        "networkInterfaces": [
    #            {
    #                "accessConfigs": [
    #                    {
    #                        "externalIp": "35.184.111.18",
    #                        "type": "ONE_TO_ONE_NAT"
    #                    }
    #                ],
    #                "dnsServers": [
    #                    "169.254.169.254"
    #                ],
    #                "forwardedIps": [],
    #                "gateway": "10.128.0.1",
    #                "ip": "10.128.0.2",
    #                "ipAliases": [],
    #                "mac": "42:01:0a:80:00:02",
    #                "network": "projects/337367557486/networks/default",
    #                "subnetmask": "255.255.240.0",
    #                "targetInstanceIps": []
    #            }
    #        ],
    #        "preempted": "FALSE",
    #        "scheduling": {
    #            "automaticRestart": "TRUE",
    #            "onHostMaintenance": "MIGRATE",
    #            "preemptible": "FALSE"
    #        },
    #        "serviceAccounts": ...
    #        },
    #        "tags": [],
    #        ...
    #        "zone": "projects/337367557486/zones/us-central1-f"
    #    },
    
    def get_meta_data(self):
        if self.__meta_data is not None:
            return self.__meta_data
        
        uri = 'http://metadata.google.internal/computeMetadata/v1/?recursive=true'
        try:
            s = httper.get(uri, headers={'Metadata-Flavor': 'Google'})
        except get_http_exceptions(), exp:
            self.logger.error('Cannot get pubic IP for your Azure instance from %s. Error: %s.Exiting' % (uri, exp))
            raise
        raw_data = json.loads(s)
        
        # We want to merge the structure into a more flatten one between compute and network
        self.__meta_data = raw_data['instance']
        
        return self.__meta_data
    
    
    def get_public_address(self):
        try:
            meta_data = self.get_meta_data()
        except Exception, exp:
            self.logger.error('Cannot get pubic IP for your Azure instance. Error: %s' % exp)
            raise
        addr = meta_data['networkInterfaces'][0]['accessConfigs'][0]['externalIp']
        return addr
