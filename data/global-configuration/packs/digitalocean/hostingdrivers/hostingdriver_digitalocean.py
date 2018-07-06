from opsbro.httpclient import get_http_exceptions, httper
from opsbro.hostingdrivermanager import InterfaceHostingDriver, HOSTING_DRIVER_LAYER_CLOUD
from opsbro.jsonmgr import jsoner

class DigitalOceanHostingDriver(InterfaceHostingDriver):
    name = 'digitalocean'
    layer = HOSTING_DRIVER_LAYER_CLOUD
    
    
    def __init__(self):
        super(DigitalOceanHostingDriver, self).__init__()
        self.__meta_data = None
    
    
    # TODO
    def is_active(self):
        return False
    
    # http://169.254.169.254/metadata/v1.json
    # {
    #  "droplet_id":1111111,
    #  "hostname":"sample-droplet",
    #  "vendor_data":"...
    #  "public_keys":["...
    #  "region":"nyc3",
    #  "interfaces":{
    #    "private":[
    #      {
    #        "ipv4":{
    #          "ip_address":"10.0.0.2",
    #          "netmask":"255.255.0.0",
    #          "gateway":"10.10.0.1"
    #        },
    #        "mac":"54:11:00:00:00:00",
    #        "type":"private"
    #      }
    #    ],
    #    "public":[
    #      {
    #        "ipv4":{
    #          "ip_address":"192.168.20.105",
    #          "netmask":"255.255.192.0",
    #          "gateway":"192.168.20.1"
    #        },
    #        "ipv6":{
    #          "ip_address":"1111:1111:0000:0000:0000:0000:0000:0000",
    #          "cidr":64,
    #          "gateway":"0000:0000:0800:0010:0000:0000:0000:0001"
    #        },
    #        "mac":"34:00:00:ff:00:00",
    #        "type":"public"}
    #    ]
    #  },
    #  "floating_ip": {
    #    "ipv4": {
    #      "active": false
    #    }
    #  },
    #  "dns":{
    #    "nameservers":[
    #      "2001:4860:4860::8844",
    #      "2001:4860:4860::8888",
    #      "8.8.8.8"
    def get_meta_data(self):
        if self.__meta_data is not None:
            return self.__meta_data
            
        uri = 'http://169.254.169.254/metadata/v1.json'
        try:
            s = httper.get(uri)
        except get_http_exceptions() as exp:
            self.logger.error('Cannot get meta data for your digital ocean instance from %s. Error: %s.Exiting' % (uri, exp))
            raise
        self.__meta_data = jsoner.loads(s)
        return self.__meta_data
    
    
    def get_public_address(self):
        try:
            meta_data = self.get_meta_data()
        except Exception as exp:
            self.logger.error('Cannot get pubic IP for your Digital Ocean instance. Error: %s' % exp)
            raise
        addr = meta_data['interfaces']['public'][0]['ipv4']['ip_address']
        return addr
    
    
    # For the unique uuid of the node, we can use the instance-id
    def get_unique_uuid(self):
        try:
            meta_data = self.get_meta_data()
        except Exception as exp:
            self.logger.error('Cannot get unique uuid for your Digital Ocean instance. Error: %s' % exp)
            raise
        addr = str(meta_data['droplet_id'])
        self.logger.info('Using DigitalOcean instance id as unique uuid for this node.')
        return addr
