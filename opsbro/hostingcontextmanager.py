import os
import sys
import json
from opsbro.httpclient import get_http_exceptions, httper
from opsbro.log import LoggerFactory

# Global logger for this part
logger = LoggerFactory.create_logger('hosting-context')


class InterfaceHostingContext(object):
    display_name = 'MISSING'
    
    
    def __init__(self):
        pass
    
    
    def is_active(self):
        raise NotImplemented()
    
    
    def get_public_address(self):
        raise NotImplemented()


class EC2HostingContext(InterfaceHostingContext):
    display_name = 'ec2'
    
    
    def __init__(self):
        super(EC2HostingContext, self).__init__()
    
    
    # We are in an EC2 host if we have the /sys/hypervisor/version/extra ending with .amazon
    def is_active(self):
        if os.path.exists('/sys/hypervisor/version/extra'):
            with open('/sys/hypervisor/version/extra') as f:
                buf = f.read().strip()
                if buf == '.amazon':
                    return True
        return False
    
    
    def get_public_address(self):
        uri = 'http://169.254.169.254/latest/meta-data/public-ipv4'
        try:
            addr = httper.get(uri)
        except get_http_exceptions(), exp:
            logger.error('Cannot get pubic IP for your EC2 instance from %s. Error: %s.Exiting' % (uri, exp))
            sys.exit(2)
        return addr


class ScalewayHostingContext(InterfaceHostingContext):
    display_name = 'scaleway'
    
    
    def __init__(self):
        super(ScalewayHostingContext, self).__init__()
    
    
    def is_active(self):
        return os.path.exists('/etc/scw-release')
    
    
    # On Scaleway need to get public IP from http://169.254.42.42/conf?format=json
    def get_public_address(self):
        uri = 'http://169.254.42.42/conf?format=json'
        try:
            s = httper.get(uri)
        except get_http_exceptions(), exp:
            logger.error('Cannot get pubic IP for your Scaleway instance from %s. Error: %s.Exiting' % (uri, exp))
            sys.exit(2)
        o = json.loads(s)
        # Example: u'public_ip': {u'dynamic': False, u'id': u'96189bf3-768f-46b1-af54-41800d695ce8', u'address': u'52.15.216.218'}
        return o['public_ip']['address']


# when you are not a cloud
class OnPremiseHostingContext(InterfaceHostingContext):
    display_name = 'on-premise'
    
    
    def __init__(self):
        super(OnPremiseHostingContext, self).__init__()
    
    
    # It's the last one, be active
    def is_active(self):
        return True
    
    
    # TODO: get default system detection
    def get_public_address(self):
        return None


# NOTE: keep the order, on premise (no cloud) must be last
context_class = [EC2HostingContext, ScalewayHostingContext, OnPremiseHostingContext]


# Try to know in which system we are running (apt, yum, or other)
# if cannot find a real backend, go to dummy that cannot find or install anything
class HostingContextMgr(object):
    def __init__(self):
        self.context = None
    
    
    def detect(self):
        for cls in context_class:
            ctx = cls()
            print "Trying context", ctx.display_name
            if ctx.is_active():
                self.context = ctx
                return
    
    
    def get_public_address(self):
        return self.context.get_public_address()


hostingcontextmgr_ = None


def get_hostingcontextmgr():
    global hostingcontextmgr_
    if hostingcontextmgr_ is None:
        logger.debug('Lazy creation of the hostingcontextmgr class')
        hostingcontextmgr_ = HostingContextMgr()
        # Launch the detection of the context
        hostingcontextmgr_.detect()
    return hostingcontextmgr_
