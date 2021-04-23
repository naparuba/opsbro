import os

from opsbro.httpclient import get_http_exceptions, httper
from opsbro.hostingdrivermanager import InterfaceHostingDriver, HOSTING_DRIVER_LAYER_CLOUD
from opsbro.jsonmgr import jsoner


class ScalewayHostingDriver(InterfaceHostingDriver):
    name = 'scaleway'
    layer = HOSTING_DRIVER_LAYER_CLOUD
    
    
    def __init__(self):
        super(ScalewayHostingDriver, self).__init__()
        self.conf = None
    
    
    def is_active(self):
        return os.path.exists('/etc/scw-release')
    
    
    def get_conf(self):
        if self.conf is not None:
            return self.conf
        
        uri = 'http://169.254.42.42/conf?format=json'
        try:
            s = httper.get(uri)
        except get_http_exceptions() as exp:
            self.logger.error('Cannot get pubic IP for your Scaleway instance from %s. Error: %s.Exiting' % (uri, exp))
            raise
        self.conf = jsoner.loads(s)
        self.logger.info('Get scaleway conf: %s' % self.conf)
        return self.conf
    
    
    # NOTE: on scaleway, if we have a mix for our nodes with other provider on the same zone, then
    # local address will be a problem
    # TODO: get a way to parameter this?
    def get_local_address(self):
        return self.get_public_address()
    
    
    # On Scaleway need to get public IP from http://169.254.42.42/conf?format=json
    def get_public_address(self):
        conf = self.get_conf()
        # Example: u'public_ip': {u'dynamic': False, u'id': u'96189bf3-768f-46b1-af54-41800d695ce8', u'address': u'52.15.216.218'}
        return conf['public_ip']['address']
    
    
    def get_unique_uuid(self):
        conf = self.get_conf()
        self.logger.info('Using the scaleway unique id as node uuid')
        return conf['id']
