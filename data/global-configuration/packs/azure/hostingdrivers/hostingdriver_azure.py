import os
import json

from opsbro.httpclient import get_http_exceptions, httper
from opsbro.hostingdrivermanager import InterfaceHostingDriver, HOSTING_DRIVER_LAYER_CLOUD


class AzureHostingDriver(InterfaceHostingDriver):
    name = 'azure'
    layer = HOSTING_DRIVER_LAYER_CLOUD
    
    def __init__(self):
        super(AzureHostingDriver, self).__init__()
        self.__meta_data = None
    
    
    # We are in an Azure host if we have the /sys/class/dmi/id/board_vendor with 'Microsoft Corporation'
    def is_active(self):
        if os.path.exists('/sys/class/dmi/id/board_vendor'):
            with open('/sys/class/dmi/id/board_vendor') as f:
                buf = f.read().strip()
                if buf == 'Microsoft Corporation':
                    return True
        return False
    
    
    # {u'compute': {u'location': u'westeurope',
    #          u'name': u'test-ubuntu',
    #          u'offer': u'UbuntuServer',
    #          u'osType': u'Linux',
    #          u'placementGroupId': u'',
    #          u'platformFaultDomain': u'0',
    #          u'platformUpdateDomain': u'0',
    #          u'publisher': u'Canonical',
    #          u'resourceGroupName': u'groupetest',
    #          u'sku': u'17.10',
    #          u'subscriptionId': u'ef6838db-2a0d-4e54-b2c7-a000c30cdb82',
    #          u'tags': u'keu1:value1;key2:value33',
    #          u'version': u'17.10.201802220',
    #          u'vmId': u'3489ed45-f7b8-4fd4-9967-fbc2457e551f',
    #          u'vmSize': u'Standard_A1'},
    # u'network': {u'interface': [{u'ipv4': {u'ipAddress': [{u'privateIpAddress': u'10.0.0.4',
    #                                                    u'publicIpAddress': u'13.95.156.4'}],
    #                                    u'subnet': [{u'address': u'10.0.0.0',
    #                                                 u'prefix': u'24'}]},
    #                          u'ipv6': {u'ipAddress': []},
    #                          u'macAddress': u'000D3A2D6367'}]}}
    def get_meta_data(self):
        if self.__meta_data is not None:
            return self.__meta_data
        
        uri = 'http://169.254.169.254/metadata/instance?api-version=2017-08-01'
        try:
            s = httper.get(uri, headers={'Metadata': 'True'})
        except get_http_exceptions(), exp:
            self.logger.error('Cannot get pubic IP for your Azure instance from %s. Error: %s.Exiting' % (uri, exp))
            raise
        raw_data = json.loads(s)
        
        # We want to merge the structure into a more flatten one between compute and network
        self.__meta_data = raw_data['compute']
        first_network_interface = raw_data['network']['interface'][0]
        self.__meta_data.update(first_network_interface)
        
        return self.__meta_data
    
    
    def get_public_address(self):
        try:
            meta_data = self.get_meta_data()
        except Exception, exp:
            self.logger.error('Cannot get pubic IP for your Azure instance. Error: %s' % exp)
            raise
        addr = meta_data['ipv4']['ipAddress'][0]['publicIpAddress']
        return addr
    
    
    # As a unique uuid we can give our vmId (that's a uuid)
    def get_unique_uuid(self):
        try:
            meta_data = self.get_meta_data()
        except Exception, exp:
            self.logger.error('Cannot get a unique uuid for your Azure instance. Error: %s' % exp)
            raise
        addr = meta_data['vmId']
        self.logger.info('Using Azure instance id as unique uuid for this node.')
        return addr
