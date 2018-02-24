import os

from opsbro.httpclient import get_http_exceptions, httper
from opsbro.hostingdrivermanager import InterfaceHostingDriver


class EC2HostingDriver(InterfaceHostingDriver):
    name = 'ec2'
    
    
    def __init__(self):
        super(EC2HostingDriver, self).__init__()
        self.__meta_data = None
    
    
    # We are in an EC2 host if we have the /sys/hypervisor/version/extra ending with .amazon
    def is_active(self):
        if os.path.exists('/sys/hypervisor/version/extra'):
            with open('/sys/hypervisor/version/extra') as f:
                buf = f.read().strip()
                if buf == '.amazon':
                    return True
        return False
    
    
    # ami-id => ami-f2d3638a
    # hostname => ip-172-31-27-231.us-west-2.compute.internal
    # instance-id => i-04aea4ef057cf6194
    # instance-type => t2.micro
    # local-hostname => ip-172-31-27-231.us-west-2.compute.internal
    # local-ipv4 => 172.31.27.231
    # placement/availability-zone => us-west-2b
    # profile => default-hvm
    # public-hostname => ec2-34-215-82-154.us-west-2.compute.amazonaws.com
    # public-ipv4 => 34.215.82.154
    # reservation-id => r-06a969361961c4bb3
    # security-groups => launch-wizard-2
    def get_meta_data(self):
        if self.__meta_data is not None:
            return self.__meta_data
        # OK we will query all meta data we want
        keys = ('ami-id ', 'hostname', 'instance-id', 'instance-type', 'local-hostname', 'local-ipv4', 'placement/availability-zone', 'profile', 'public-hostname',
                'public-ipv4', 'reservation-id', 'security-groups')
        self.__meta_data = {}
        for k in keys:
            # For placement, only take the availability-zone
            uri_k = k
            if '/' in k:
                k = k.split('/')[-1]
            uri = 'http://169.254.169.254/latest/meta-data/%s' % uri_k
            # Note: each call is quite fast, not a problem to get them all at daemon startup
            v = httper.get(uri)
            self.__meta_data[k] = v
        
        # Note that the region is the  minus the last character
        self.__meta_data['region'] = self.__meta_data['availability-zone'][:-1]
        return self.__meta_data
    
    
    def get_public_address(self):
        try:
            meta_data = self.get_meta_data()
        except Exception, exp:
            self.logger.error('Cannot get pubic IP for your EC2 instance. Error: %s' % exp)
            raise
        addr = meta_data['public-ipv4']
        return addr
