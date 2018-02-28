import os

from opsbro.httpclient import get_http_exceptions, httper
from opsbro.hostingdrivermanager import InterfaceHostingDriver, HOSTING_DRIVER_LAYER_CLOUD


class AlibabaHostingDriver(InterfaceHostingDriver):
    name = 'alibaba'
    layer = HOSTING_DRIVER_LAYER_CLOUD
    
    
    def __init__(self):
        super(AlibabaHostingDriver, self).__init__()
        self.__meta_data = None
    
    
    # TODO
    def is_active(self):
        return False
    
    
    # region-id => cn-shenzhen
    # zone-id => cn-shenzhen-a
    # instance-id => i-04aea4ef057cf6194
    # CF: https://help.aliyun.com/knowledge_detail/49122.html
    def get_meta_data(self):
        if self.__meta_data is not None:
            return self.__meta_data
        # OK we will query all meta data we want
        keys = ('region-id', 'zone-id', 'instance-id', 'image-id', 'private-ipv4', 'public-ipv4')
        self.__meta_data = {}
        for k in keys:
            uri = 'http://100.100.100.200/latest/meta-data/%s' % k
            # Note: each call is quite fast, not a problem to get them all at daemon startup
            v = httper.get(uri)
            self.__meta_data[k] = v
        
        return self.__meta_data
    
    
    def get_public_address(self):
        try:
            meta_data = self.get_meta_data()
        except Exception, exp:
            self.logger.error('Cannot get pubic IP for your Alibaba instance. Error: %s' % exp)
            raise
        addr = meta_data['public-ipv4']
        return addr
    
    
    # For the unique uuid of the node, we can use the instance-id
    def get_unique_uuid(self):
        try:
            meta_data = self.get_meta_data()
        except Exception, exp:
            self.logger.error('Cannot get unique uuid for your Alibaba instance. Error: %s' % exp)
            raise
        addr = meta_data['instance-id']
        self.logger.info('Using Alibaba instance id as unique uuid for this node.')
        return addr
