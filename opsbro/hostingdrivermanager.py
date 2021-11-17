import os
import glob
import imp
import socket
import sys
import time

try:
    import fcntl
except ImportError:
    fcntl = None
import struct

if os.name == 'nt':
    from .misc.windows import windowser
from opsbro.log import LoggerFactory, DEFAULT_LOG_PART
from .misc.six import add_metaclass
from .util import string_decode, my_sort, exec_command, my_cmp, unicode_to_bytes

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
        # tuning: we want to avoid to call
        self._hostname_i_execution_fail = 0.0
        self._hostname_i_execution_period = 300  # if the hostname execution call did fail, do not allow it until this seconds
    
    
    def is_active(self):
        raise NotImplemented()
    
    
    # Get the ip address in a linux system
    def __get_ip_address(self, ifname):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,  # SIOCGIFADDR
            struct.pack('256s', unicode_to_bytes(ifname[:15]))
        )[20:24])
    
    
    def _get_linux_local_addresses(self):
        res = []
        now = time.time()
        # If hostname -I command did fail before, we should not hammer it (some system like alpine or embedded
        # do not have the -I option)
        if now > self._hostname_i_execution_fail + self._hostname_i_execution_period:
            try:
                rc, stdout, stderr = exec_command('hostname -I')
                self._hostname_i_execution_fail = 0.0
            except Exception as exp:
                logger.info('Cannot use the hostname -I call for linux (%s), trying to guess local addresses' % exp)
                stdout = ''
                self._hostname_i_execution_fail = now
            buf = string_decode(stdout).strip()
            res = [s.strip() for s in buf.split(' ') if s.strip()]
        
        # Some system like in alpine linux that don't have hostname -I call so try to guess
        if len(res) == 0:
            logger.debug('Cannot use the hostname -I call for linux, trying to guess local addresses')
            for prefi in ('bond', 'eth', 'venet', 'wlan'):
                for i in range(0, 10):
                    ifname = '%s%d' % (prefi, i)
                    try:
                        addr = self.__get_ip_address(ifname)
                        res.append(addr)
                    except IOError:  # no such interface
                        pass
        res = my_sort(res, cmp_f=self._sort_local_addresses)  # beware: python3 have special cmp
        return res
    
    
    def _is_valid_local_addr(self, addr):
        if not addr:
            return False
        if addr.startswith('127.0.0.'):
            return False
        if addr.startswith('169.254.'):
            return False
        # we can check the address is localy available
        if sys.platform.startswith('linux'):  # linux2 for python2, linux for python3
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
        addr1_is_127 = addr1.startswith('127.0.')
        addr2_is_127 = addr2.startswith('127.0.')
        
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
    
    
    @staticmethod
    def _match_mask(ip, mask_filter):
        if mask_filter:
            return ip in mask_filter
        return True
    
    
    def _get_address(self, ip_mask):
        mask_filter = None
        if ip_mask is not None:
            from opsbro.misc.IPy import IP
            try:
                mask_filter = IP(ip_mask)
            except Exception as exp:
                # Major error, need to exit
                err = 'Cannot load the ip mask: %s: %s. Exiting' % (ip_mask, exp)
                daemon_logger = LoggerFactory.create_logger(DEFAULT_LOG_PART)
                logger_crash = LoggerFactory.create_logger('crash')
                logger.errro(err)
                logger_crash.error(err)
                daemon_logger.error('err')
                sys.exit(2)
        
        # If I am in the DNS or in my /etc/hosts, I win
        try:
            addr = socket.gethostbyname(socket.gethostname())
            if self._is_valid_local_addr(addr) and self._match_mask(addr, mask_filter):
                return addr
        except Exception as exp:
            pass
        
        if sys.platform.startswith('linux'):  # linux2 for python2, linux for python3
            addrs = self._get_linux_local_addresses()
            # Return the first that match mask_filter, or just the first
            for addr in addrs:
                if self._match_mask(addr, mask_filter):
                    return addr
        
        # On windows also loop over the interfaces
        if os.name == 'nt':
            c = windowser.get_wmi()
            for interface in c.Win32_NetworkAdapterConfiguration(IPEnabled=1):
                for addr in interface.IPAddress:
                    if self._is_valid_local_addr(addr):
                        return addr
        return None
    
    
    # If we do not have a specific hoster, we look at the most
    # important interface, by avoiding useless interfaces like
    # locals or dhcp not active
    def get_local_address(self):
        ip_mask = os.environ.get('OPSBRO_LOCAL_NETWORK', None)
        return self._get_address(ip_mask)
    
    
    # If we are not in a cloud or something, our public == best local address
    def get_public_address(self):
        ip_mask = os.environ.get('OPSBRO_PUBLIC_NETWORK', None)
        return self._get_address(ip_mask)
    
    
    def get_unique_uuid(self):
        product_uuid_p = '/sys/class/dmi/id/product_uuid'
        # Be sure not to be in a docket container, if so, will be host dmi
        # even if the user did disable docker pack
        if os.path.exists(product_uuid_p) and not os.path.exists('/.dockerenv'):
            with open(product_uuid_p, 'r') as f:
                buf = f.read().strip()
            # some manufacturers fake bios uuid, by starting with 12345678, if so, cannot use it, and prefer a local file uuid
            if buf.startswith('12345678'):
                self.logger.warning('[SERVER-UUID] we cannot use the the DMI (bios) uuid as server unique UUID because it seems it is a fake one: %s' % buf.lower())
            else:  # OK looks as a valid uuid
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
            return my_cmp(cls1.name, cls2.name)
        return my_cmp(cls1.layer, cls2.layer)
    
    
    def detect(self):
        # First get all Hosting driver class available
        hostingctx_clss = InterfaceHostingDriver.get_sub_class()
        
        # Get first cloud > virtualisation > plysical > default > unset
        hostingctx_clss = my_sort(hostingctx_clss, cmp_f=self.__default_last)  # beware: python3 have special cmp
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
