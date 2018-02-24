import os
import glob
import imp
import socket
import sys

try:
    import fcntl
except ImportError:
    fcntl = None
import struct

from opsbro.misc.windows import windowser
from opsbro.log import LoggerFactory

# Global logger for this part
logger = LoggerFactory.create_logger('hosting-driver')


# Base class for hosting driver. MUST be used
class InterfaceHostingDriver(object):
    name = '__MISSING__NAME__'
    is_default = False
    
    class __metaclass__(type):
        __inheritors__ = set()
        
        
        def __new__(meta, name, bases, dct):
            klass = type.__new__(meta, name, bases, dct)
            # When creating the class, we need to look at the module where it is. It will be create like this (in collectormanager)
            # collector___global___windows___collector_iis ==> level=global  pack_name=windows, collector_name=collector_iis
            from_module = dct['__module__']
            elts = from_module.split('___')
            # Note: the master class InterfaceHostingDriver will go in this too, but its module won't match the ___ filter
            if len(elts) != 1:
                # Let the klass know it
                klass.pack_level = elts[1]
                klass.pack_name = elts[2]
            
            meta.__inheritors__.add(klass)
            return klass
    
    @classmethod
    def get_sub_class(cls):
        return cls.__inheritors__
    
    
    def __init__(self):
        self.logger = logger
    
    
    def is_active(self):
        raise NotImplemented()
    
    
    # Get the ip address in a linux system
    def __get_ip_address(self, ifname):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', ifname[:15])
        )[20:24])
    
    
    def _get_linux_local_addresses(self):
        stdin, stdout = os.popen2('hostname -I')
        buf = stdout.read().strip()
        stdin.close()
        stdout.close()
        res = [s.strip() for s in buf.split(' ') if s.strip()]
        
        # Some system like in alpine linux that don't have hostname -I call
        # so try to guess
        if len(res) == 0:
            logger.info('Cannot use the hostname -I call for linux, trying to guess local addresses')
            for prefi in ['bond', 'eth', 'venet']:
                for i in xrange(0, 10):
                    ifname = '%s%d' % (prefi, i)
                    try:
                        addr = self.__get_ip_address(ifname)
                        res.append(addr)
                    except IOError:  # no such interface
                        pass
        
        res.sort(self._sort_local_addresses)
        return res
    
    
    def _is_valid_local_addr(self, addr):
        if not addr:
            return False
        if addr.startswith('127.0.0.'):
            return False
        if addr.startswith('169.254.'):
            return False
        # we can check the address is localy available
        if sys.platform == 'linux2':
            _laddrs = self._get_linux_local_addresses()
            if addr not in _laddrs:
                return False
        return True
    
    
    def _sort_local_addresses(self, addr1, addr2):
        addr1_is_192 = addr1.startswith('192.')
        addr2_is_192 = addr2.startswith('192.')
        addr1_is_10 = addr1.startswith('10.')
        addr2_is_10 = addr2.startswith('10.')
        addr1_is_172 = addr1.startswith('172.')
        addr2_is_172 = addr2.startswith('172.')
        addr1_is_127 = addr1.startswith('127.')
        addr2_is_127 = addr2.startswith('127.')
        
        # lower is better
        addr1_order = 4
        if addr1_is_192:
            addr1_order = 1
        elif addr1_is_172:
            addr1_order = 2
        elif addr1_is_10:
            addr1_order = 3
        if addr1_is_127:
            addr1_order = 5
        addr2_order = 4
        if addr2_is_192:
            addr2_order = 1
        elif addr2_is_172:
            addr2_order = 2
        elif addr2_is_10:
            addr2_order = 3
        if addr2_is_127:
            addr2_order = 5
        
        if addr1_order > addr2_order:
            return 1
        elif addr1_order < addr2_order:
            return -1
        return 0
    
    
    # If we do not have a specific hoster, we look at the most
    # important interface, by avoiding useless interfaces like
    # locals or dhcp not active
    def get_public_address(self):
        # If I am in the DNS or in my /etc/hosts, I win
        try:
            addr = socket.gethostbyname(socket.gethostname())
            if self._is_valid_local_addr(addr):
                return addr
        except Exception, exp:
            pass
        
        if sys.platform == 'linux2':
            addrs = self._get_linux_local_addresses()
            if len(addrs) > 0:
                return addrs[0]
        
        # On windows also loop over the interfaces
        if os.name == 'nt':
            c = windowser.get_wmi()
            for interface in c.Win32_NetworkAdapterConfiguration(IPEnabled=1):
                for addr in interface.IPAddress:
                    if self._is_valid_local_addr(addr):
                        return addr
        return None


# when you are not a cloud
class OnPremiseHostingDriver(InterfaceHostingDriver):
    name = 'on-premise'
    is_default = True
    
    
    def __init__(self):
        super(OnPremiseHostingDriver, self).__init__()
    
    
    # It's the last one, be active
    def is_active(self):
        return True


# Try to know in which system we are running (apt, yum, or other)
# if cannot find a real backend, go to dummy that cannot find or install anything
class HostingDriverMgr(object):
    def __init__(self):
        self.driver = None
    
    
    def __default_last(self, cls1, cls2):
        if cls1.is_default:
            return 1
        if cls2.is_default:
            return -1
        return 0
    
    
    def detect(self):
        # First get all Hosting driver class available
        hostingctx_clss = InterfaceHostingDriver.get_sub_class()
        
        hostingctx_clss = sorted(hostingctx_clss, cmp=self.__default_last)
        
        for cls in hostingctx_clss:
            # skip base module Collector
            if cls == InterfaceHostingDriver:
                continue
            
            ctx = cls()
            logger.debug('Trying hosting driver %s' % ctx.name)
            if ctx.is_active():
                self.driver = ctx
                logger.debug('Hosting driver is founded: %s' % ctx.name)
                return
    
    
    def load_directory(self, directory, pack_name='', pack_level=''):
        logger.debug('Loading hosting driver directory at %s for pack %s' % (directory, pack_name))
        pth = directory + '/hostingdriver_*.py'
        collector_files = glob.glob(pth)
        for f in collector_files:
            fname = os.path.splitext(os.path.basename(f))[0]
            logger.debug('Loading hosting driver from file %s' % f)
            try:
                # NOTE: KEEP THE ___ as they are used to let the class INSIDE te module in which pack/level they are. If you have
                # another way to give the information to the inner class inside, I take it ^^
                m = imp.load_source('hostingdriver___%s___%s___%s' % (pack_level, pack_name, fname), f)
                logger.debug('Hosting driver module loaded: %s' % m)
            except Exception, exp:
                logger.error('Cannot load hosting driver %s: %s' % (fname, exp))
    
    
    def get_public_address(self):
        return self.driver.get_public_address()
    
    
    def is_driver_active(self, driver_name):
        return self.driver.name == driver_name
    
    
    def get_driver(self):
        return self.driver
    
    
    def get_driver_name(self):
        if self.driver is None:
            return ''
        return self.driver.name


hostingdrivermgr_ = None


def get_hostingdrivermgr():
    global hostingdrivermgr_
    if hostingdrivermgr_ is None:
        logger.debug('Lazy creation of the hostingdrivermgr class')
        hostingdrivermgr_ = HostingDriverMgr()
        # Launch the detection of the driver
        hostingdrivermgr_.detect()
    return hostingdrivermgr_
