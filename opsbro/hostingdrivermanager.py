import os
import glob
import imp
import socket
import sys

PY3 = sys.version_info >= (3,)
if PY3:
    def cmp(a, b):
        return ((a > b) - (a < b))
try:
    import fcntl
except ImportError:
    fcntl = None
import struct

from .misc.windows import windowser
from .log import LoggerFactory
from .misc.six import add_metaclass

# Global logger for this part
logger = LoggerFactory.create_logger('hosting-driver')

# From the most specific to the most generic
HOSTING_DRIVER_LAYER_CONTAINER = 1
HOSTING_DRIVER_LAYER_VIRTUALISATION = 2
HOSTING_DRIVER_LAYER_CLOUD = 3
HOSTING_DRIVER_LAYER_PHYSICAL = 4
HOSTING_DRIVER_LAYER_DEFAULT = 5
HOSTING_DRIVER_LAYER_UNSET = 6


class HostingDriverMetaclass(type):
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


@add_metaclass(HostingDriverMetaclass)
# Base class for hosting driver. MUST be used
class InterfaceHostingDriver(object):
    name = '__MISSING__NAME__'
    is_default = False
    layer = HOSTING_DRIVER_LAYER_UNSET
    
    
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
    def get_local_address(self):
        # If I am in the DNS or in my /etc/hosts, I win
        try:
            addr = socket.gethostbyname(socket.gethostname())
            if self._is_valid_local_addr(addr):
                return addr
        except Exception as exp:
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
    
    
    # If we are not in a cloud or something, our public == best local address
    def get_public_address(self):
        return self.get_local_address()
    
    
    def get_unique_uuid(self):
        product_uuid_p = '/sys/class/dmi/id/product_uuid'
        # Be sure not to be in a docket container, if so, will be host dmi
        # even if the user did disable docker pack
        if os.path.exists(product_uuid_p) and not os.path.exists('/.dockerenv'):
            with open(product_uuid_p, 'r') as f:
                buf = f.read().strip()
            self.logger.info('[SERVER-UUID] using the DMI (bios) uuid as server unique UUID: %s' % buf.lower())
            return buf
        
        # windows: we ask to WMI for the baord serial number
        if os.name == 'nt':
            c = windowser.get_wmi()
            boards = c.Win32_BaseBoard()  # NOTE: somve VM in cloud do not even have a board...
            if len(boards) == 0:
                self.logger.error('[SERVER-UUID] Cannot get the unique bios/board serial number as no mother board is present in WMI')
            else:
                board = c.Win32_BaseBoard()[0]
                try:
                    buf = board.SerialNumber.strip().lower()
                    self.logger.info('[SERVER-UUID] using the DMI (bios) uuid as server unique UUID: %s' % buf)
                    return buf
                except AttributeError as exp:
                    self.logger.error('[SERVER-UUID] Cannot get the unique bios/board serial number: %s' % exp)
        
        # Cannot find: we will have to guess it
        return None


# when you are not a cloud
class OnPremiseHostingDriver(InterfaceHostingDriver):
    name = 'on-premise'
    is_default = True
    layer = HOSTING_DRIVER_LAYER_DEFAULT
    
    
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
        self.drivers = []  # order is important
    
    
    def __default_last(self, cls1, cls2):
        if cls1.layer == cls2.layer:
            return cmp(cls1.name, cls2.name)
        return cmp(cls1.layer, cls2.layer)
    
    
    def detect(self):
        # First get all Hosting driver class available
        hostingctx_clss = InterfaceHostingDriver.get_sub_class()
        
        # Get first cloud > virtualisation > plysical > default > unset
        if not PY3:
            hostingctx_clss = sorted(hostingctx_clss, cmp=self.__default_last)
        else:
            from functools import cmp_to_key
            hostingctx_clss = sorted(hostingctx_clss, key=cmp_to_key(self.__default_last))
        for cls in hostingctx_clss:
            # skip base module Collector
            if cls == InterfaceHostingDriver:
                continue
            
            ctx = cls()
            logger.debug('Trying hosting driver %s' % ctx.name)
            self.drivers.append(ctx)
        
        for drv in self.drivers:
            if drv.is_active():
                self.driver = drv
                logger.debug('Hosting driver is founded: %s' % drv.name)
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
            except Exception as exp:
                logger.error('Cannot load hosting driver %s: %s' % (fname, exp))
    
    
    def get_local_address(self):
        return self.driver.get_local_address()
    
    
    def get_public_address(self):
        return self.driver.get_public_address()
    
    
    def get_unique_uuid(self):
        return self.driver.get_unique_uuid()
    
    
    def is_driver_active(self, driver_name):
        drv = self.get_driver(driver_name)
        if drv is None:
            return False
        return drv.is_active()
    
    
    def get_driver(self, name):
        for drv in self.drivers:
            if drv.name == name:
                return drv
        return None
    
    
    def get_driver_name(self):
        if self.driver is None:
            return ''
        return self.driver.name
    
    
    def get_drivers_state(self):
        r = []  # order is important
        for drv in self.drivers:
            e = {'name': drv.name, 'is_active': drv.is_active()}
            r.append(e)
        return r


hostingdrivermgr_ = None


def get_hostingdrivermgr():
    global hostingdrivermgr_
    if hostingdrivermgr_ is None:
        logger.debug('Lazy creation of the hostingdrivermgr class')
        hostingdrivermgr_ = HostingDriverMgr()
        # NOTE: the detection of the driver will be done by the launcher
    return hostingdrivermgr_
