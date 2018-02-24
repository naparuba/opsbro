import os
import json

from opsbro.httpclient import get_http_exceptions, httper
from opsbro.hostingdrivermanager import InterfaceHostingDriver


class ScalewayHostingDriver(InterfaceHostingDriver):
    name = 'scaleway'
    
    
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
        except get_http_exceptions(), exp:
            self.logger.error('Cannot get pubic IP for your Scaleway instance from %s. Error: %s.Exiting' % (uri, exp))
            raise
        self.conf = json.loads(s)
        self.logger.info('Get scaleway conf: %s' % self.conf)
        return  self.conf
    
    # On Scaleway need to get public IP from http://169.254.42.42/conf?format=json
    def get_public_address(self):
        conf = self.get_conf()
        # Example: u'public_ip': {u'dynamic': False, u'id': u'96189bf3-768f-46b1-af54-41800d695ce8', u'address': u'52.15.216.218'}
        return conf['public_ip']['address']
