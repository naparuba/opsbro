import os
import traceback

from opsbro.collector import Collector


def _get_interface_klass():  # Lazy load
    import os
    
    if os.name == 'nt':  # not manage on windows
        return None
    
    import socket
    from binascii import hexlify
    
    from ctypes import (
        Structure, Union, c_ushort, c_void_p, c_int, c_uint16, c_uint32, c_uint8, c_short, c_ulong, c_ubyte, string_at
    )
    
    import fcntl
    import struct
    
    # Complete list of InterfaceReq flags for linux as of2013
    
    IFF_UP = 0x1
    IFF_BROADCAST = 0x2
    IFF_DEBUG = 0x4
    IFF_LOOPBACK = 0x8
    IFF_POINTOPOINT = 0x10
    IFF_NOTRAILERS = 0x20
    IFF_RUNNING = 0x40
    IFF_NOARP = 0x80
    IFF_PROMISC = 0x100
    IFF_ALLMULTI = 0x200
    IFF_MASTER = 0x400
    IFF_SLAVE = 0x800
    IFF_MULTICAST = 0x1000
    IFF_PORTSEL = 0x2000
    IFF_AUTOMEDIA = 0x4000
    IFF_DYNAMIC = 0x8000
    
    IFNAMSIZ = 16
    IFHWADDRLEN = 6
    
    # Incomplete list of most IOCTLs used to control interfaces
    
    # ['const', 'struct', 'rtentry', '*', '//', 'MORE']
    SIOCADDRT = 0x0000890B
    # ['const', 'struct', 'rtentry', '*', '//', 'MORE']
    SIOCDELRT = 0x0000890C
    # ['char', '[]']
    SIOCGIFNAME = 0x00008910
    # ['void']
    SIOCSIFLINK = 0x00008911
    # ['struct', 'ifconf', '*', '//', 'MORE', '//', 'I-O']
    SIOCGIFCONF = 0x00008912
    # ['struct', 'InterfaceReq', '*', '//', 'I-O']
    SIOCGIFFLAGS = 0x00008913
    # ['const', 'struct', 'InterfaceReq', '*']
    SIOCSIFFLAGS = 0x00008914
    # [ifr_ifindex]
    SIOCGIFINDEX = 0x00008933
    # ['struct', 'InterfaceReq', '*', '//', 'I-O']
    SIOCGIFADDR = 0x00008915
    # ['const', 'struct', 'InterfaceReq', '*']
    SIOCSIFADDR = 0x00008916
    # ['struct', 'InterfaceReq', '*', '//', 'I-O']
    SIOCGIFDSTADDR = 0x00008917
    # ['const', 'struct', 'InterfaceReq', '*']
    SIOCSIFDSTADDR = 0x00008918
    # ['struct', 'InterfaceReq', '*', '//', 'I-O']
    SIOCGIFBRDADDR = 0x00008919
    # ['const', 'struct', 'InterfaceReq', '*']
    SIOCSIFBRDADDR = 0x0000891A
    # ['struct', 'InterfaceReq', '*', '//', 'I-O']
    SIOCGIFNETMASK = 0x0000891B
    # ['const', 'struct', 'InterfaceReq', '*']
    SIOCSIFNETMASK = 0x0000891C
    # ['struct', 'InterfaceReq', '*', '//', 'I-O']
    SIOCGIFMETRIC = 0x0000891D
    # ['const', 'struct', 'InterfaceReq', '*']
    SIOCSIFMETRIC = 0x0000891E
    # ['struct', 'InterfaceReq', '*', '//', 'I-O']
    SIOCGIFMEM = 0x0000891F
    # ['const', 'struct', 'InterfaceReq', '*']
    SIOCSIFMEM = 0x00008920
    # ['struct', 'InterfaceReq', '*', '//', 'I-O']
    SIOCGIFMTU = 0x00008921
    # ['const', 'struct', 'InterfaceReq', '*']
    SIOCSIFMTU = 0x00008922
    # ['struct', 'InterfaceReq', '*', '//', 'I-O']
    OLD_SIOCGIFHWADDR = 0x00008923
    # ['const', 'struct', 'InterfaceReq', '*', '//', 'MORE']
    SIOCSIFHWADDR = 0x00008924
    # ['int', '*']
    SIOCGIFENCAP = 0x00008925
    # ['const', 'int', '*']
    SIOCSIFENCAP = 0x00008926
    # ['struct', 'InterfaceReq', '*', '//', 'I-O']
    SIOCGIFHWADDR = 0x00008927
    # ['void']
    SIOCGIFSLAVE = 0x00008929
    # ['void']
    SIOCSIFSLAVE = 0x00008930
    # ['const', 'struct', 'InterfaceReq', '*']
    SIOCADDMULTI = 0x00008931
    # ['const', 'struct', 'InterfaceReq', '*']
    SIOCDELMULTI = 0x00008932
    # ['void']
    SIOCADDRTOLD = 0x00008940
    # ['void']
    SIOCDELRTOLD = 0x00008941
    # ['ifr_ifqlen']
    SIOCGIFTXQLEN = 0x00008942
    # ['ifr_ifqlen']
    SIOCSIFTXQLEN = 0x00008943
    # ['const', 'struct', 'arpreq', '*']
    SIOCDARP = 0x00008950
    # ['struct', 'arpreq', '*', '//', 'I-O']
    SIOCGARP = 0x00008951
    # ['const', 'struct', 'arpreq', '*']
    SIOCSARP = 0x00008952
    # ['const', 'struct', 'arpreq', '*']
    SIOCDRARP = 0x00008960
    # ['struct', 'arpreq', '*', '//', 'I-O']
    SIOCGRARP = 0x00008961
    # ['const', 'struct', 'arpreq', '*']
    SIOCSRARP = 0x00008962
    # ['struct', 'InterfaceReq', '*', '//', 'I-O']
    SIOCGIFMAP = 0x00008970
    # ['const', 'struct', 'InterfaceReq', '*']
    SIOCSIFMAP = 0x00008971
    
    FLAGS = {
        IFF_UP         : 'up',  # 'Interface is up',
        IFF_BROADCAST  : 'broadcast',  # 'Broadcast address valid',
        IFF_DEBUG      : 'debug',  # 'Turn on debugging',
        IFF_LOOPBACK   : 'loopback',  # 'Is a loopback net',
        IFF_POINTOPOINT: 'point_to_point',  # 'Interface is point-to-point link',
        IFF_NOTRAILERS : 'no_trailers',  # 'Avoid use of trailers',
        IFF_RUNNING    : 'running',  # 'Resources allocated',
        IFF_NOARP      : 'no_arp',  # 'No address resolution protocol',
        IFF_PROMISC    : 'promisc',  # 'Receive all packets',
        IFF_ALLMULTI   : 'promisc_multicast',  # 'Receive all multicast packets',
        IFF_MASTER     : 'master',  # 'Master of a load balancer',
        IFF_SLAVE      : 'slave',  # 'Slave of a load balancer',
        IFF_MULTICAST  : 'multicast',  # 'Supports multicast',
        IFF_PORTSEL    : 'portsel',  # 'Can set media type',
        IFF_AUTOMEDIA  : 'automedia',  # 'Auto media select active',
        IFF_DYNAMIC    : 'dynamic',  # 'Dialup device with changing addresses'
    }
    
    class SockAddr_Gen(Structure):
        _fields_ = [
            ("sa_family", c_uint16),
            ("sa_data", (c_uint8 * 22))
        ]
    
    # AF_INET / IPv4
    class IPv4(Structure):
        _pack_ = 1
        _fields_ = [
            ("s_addr", c_uint32),
        ]
    
    class SockAddr_IPv4(Structure):
        _pack_ = 1
        _fields_ = [
            ("sin_family", c_ushort),
            ("sin_port", c_ushort),
            ("sin_addr", IPv4),
            ("sin_zero", (c_uint8 * 16)),  # padding
        ]
    
    # AF_INET6 / IPv6
    class IPv6_U(Union):
        _pack_ = 1
        _fields_ = [
            ("u6_addr8", (c_uint8 * 16)),
            ("u6_addr16", (c_uint16 * 8)),
            ("u6_addr32", (c_uint32 * 4))
        ]
    
    class IPv6_Addr(Structure):
        _pack_ = 1
        _fields_ = [
            ("IPv6_U", IPv6_U),
        ]
    
    class SockAddr_IPv6(Structure):
        _pack_ = 1
        _fields_ = [
            ("sin6_family", c_short),
            ("sin6_port", c_ushort),
            ("sin6_flowinfo", c_uint32),
            ("sin6_addr", IPv6_Addr),
            ("sin6_scope_id", c_uint32),
        ]
    
    # AF_LINK / BSD|OSX
    class SockAddr_Dl(Structure):
        _fields_ = [
            ("sdl_len", c_uint8),
            ("sdl_family", c_uint8),
            ("sdl_index", c_uint16),
            ("sdl_type", c_uint8),
            ("sdl_nlen", c_uint8),
            ("sdl_alen", c_uint8),
            ("sdl_slen", c_uint8)
        ]
    
    class SockAddr(Union):
        _pack_ = 1
        _fields_ = [
            ('gen', SockAddr_Gen),
            ('in4', SockAddr_IPv4),
            ('in6', SockAddr_IPv6)
        ]
    
    class InterfaceMap(Structure):
        _pack_ = 1
        _fields_ = [
            ('mem_start', c_ulong),
            ('mem_end', c_ulong),
            ('base_addr', c_ushort),
            ('irq', c_ubyte),
            ('dma', c_ubyte),
            ('port', c_ubyte)
        ]
    
    class InterfaceData(Union):
        _pack_ = 1
        _fields_ = [
            ('ifr_addr', SockAddr),
            ('ifr_dstaddr', SockAddr),
            ('ifr_broadaddr', SockAddr),
            ('ifr_netmask', SockAddr),
            ('ifr_hwaddr', SockAddr),
            ('ifr_flags', c_short),
            ('ifr_ifindex', c_int),
            ('ifr_ifqlen', c_int),
            ('ifr_metric', c_int),
            ('ifr_mtu', c_int),
            ('ifr_map', InterfaceMap),
            ('ifr_slave', (c_ubyte * IFNAMSIZ)),
            ('ifr_newname', (c_ubyte * IFNAMSIZ)),
            ('InterfaceData', c_void_p)
        ]
    
    class InterfaceReq(Structure):
        _pack_ = 1
        _fields_ = [
            ('ifr_name', (c_ubyte * IFNAMSIZ)),
            ('data', InterfaceData)
        ]
    
    class Interface(object):
        """
        Represents a network interface.

        Almost all interesting attributes are exported in the form
        of a variable. You can get this variable. For example:

        ifeth0 = Interface("eth0")
        print ifeth0.addr  # will print the current address
        """
        
        
        def __init__(self, index=1, name=None):
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
            fcntl.fcntl(
                self.sock,
                fcntl.F_SETFD,
                fcntl.fcntl(self.sock, fcntl.F_GETFD) | fcntl.FD_CLOEXEC
            )
            
            self._index = index
            self._name = name
            
            # Get the name of the interface
            if self._name is None:
                self._name = self.name
            else:
                self._name = (c_ubyte * IFNAMSIZ)(*bytearray(self._name))
                self._index = self.index
        
        
        def __newIfreqWithName(self):
            ifr = InterfaceReq()
            ifr.ifr_name = self._name
            return ifr
        
        
        def __doIoctl(self, ifr, SIOC, mutate=True):
            try:
                fcntl.ioctl(self.sock, SIOC, ifr, mutate)
            except IOError as ioException:
                if ioException.errno == 99:
                    pass
                else:
                    raise ioException
        
        
        def __getSimple(self, ioctl, element):
            ifr = self.__newIfreqWithName()
            self.__doIoctl(ifr, ioctl)
            
            element = element.split('.')
            tmp = ifr
            for item in element:
                tmp = getattr(tmp, item)
            
            return tmp
        
        
        def __setSimple(self, ioctl, element, val):
            ifr = self.__newIfreqWithName()
            
            element = element.split('.')
            tmp = ifr
            
            for item in element[:-1]:
                tmp = getattr(tmp, item)
            
            setattr(tmp, element[-1], val)
            self.__doIoctl(ifr, ioctl)
        
        
        @property
        def index(self):
            ifr = self.__newIfreqWithName()
            self.__doIoctl(ifr, SIOCGIFINDEX)
            self._index = ifr.data.ifr_ifindex
            return self._index
        
        
        @property
        def name(self):
            ifr = InterfaceReq()
            ifr.data.ifr_ifindex = self._index
            self.__doIoctl(ifr, SIOCGIFNAME)
            self._name = ifr.ifr_name
            return string_at(self._name)
        
        
        @property
        def flags(self):
            return self.__getSimple(SIOCGIFFLAGS, 'data.ifr_flags')
        
        
        @property
        def ifqlen(self):
            return self.__getSimple(SIOCGIFTXQLEN, 'data.ifr_ifqlen')
        
        
        @property
        def metric(self):
            return self.__getSimple(SIOCGIFMETRIC, 'data.ifr_metric')
        
        
        @property
        def mtu(self):
            return self.__getSimple(SIOCGIFMTU, 'data.ifr_mtu')
        
        
        @property
        def hwaddr(self):
            ifr = self.__newIfreqWithName()
            self.__doIoctl(ifr, SIOCGIFHWADDR)
            hw = ifr.data.ifr_hwaddr.gen.sa_data
            
            self._hwaddr = ''
            for i in hw[:IFHWADDRLEN]:
                self._hwaddr = self._hwaddr + '%.2X:' % i
            
            return self._hwaddr[:-1]
        
        
        @property
        def addr(self):
            ifr = self.__newIfreqWithName()
            self.__doIoctl(ifr, SIOCGIFADDR)
            return ifr.data.ifr_addr
        
        
        @property
        def broadaddr(self):
            ifr = self.__newIfreqWithName()
            self.__doIoctl(ifr, SIOCGIFBRDADDR)
            return ifr.data.ifr_broadaddr
        
        
        @property
        def netmask(self):
            ifr = self.__newIfreqWithName()
            self.__doIoctl(ifr, SIOCGIFNETMASK)
            return ifr.data.ifr_netmask
        
        
        def __getSinAddr(self, sockaddr):
            if sockaddr.gen.sa_family == socket.AF_INET:
                return sockaddr.in4.sin_addr.s_addr
            if sockaddr.gen.sa_family == socket.AF_INET6:
                return sockaddr.in6.sin6_addr.in6_u
            return 0
        
        
        def __sockaddrFromTuple(self, inVal):
            if inVal[0] == socket.AF_INET:
                sin4 = SockAddr()
                
                sin4.in4.sin_family = inVal[0]
                sin4.in4.sin_addr.s_addr = struct.unpack(
                    '<L', socket.inet_pton(
                        inVal[0],
                        inVal[1]
                    )
                )[0]
                return sin4
            
            elif inVal[0] == socket.AF_INET6:
                sin6 = SockAddr()
                sin6.in6.sin6_family = inVal[0]
                sin6.in6.sin6_addr.in6_u = hexlify(
                    socket.inet_pton(
                        inVal[0],
                        inVal[1]
                    )
                )
                return sin6
        
        
        def __sockaddrToStr(self, sockaddr):
            if sockaddr.gen.sa_family == 0:
                return 'None'
            
            p = struct.pack('<L', self.__getSinAddr(sockaddr))
            return socket.inet_ntop(sockaddr.gen.sa_family, p)
        
        
        def readableFlags(self, flag):
            _flags = {}
            for k in list(FLAGS.keys()):
                if flag & k:
                    _flags[FLAGS[k]] = True
            return _flags
        
        
        def _iface2dict(self):
            r = {
                'interface'        : self.name,
                'index'            : self._index,
                'hardware_address' : self.hwaddr,
                'ip_address'       : self.__sockaddrToStr(self.addr),
                'broadcast_address': self.__sockaddrToStr(self.broadaddr),
                'net_mask'         : self.__sockaddrToStr(self.netmask),
                'mtu'              : self.mtu,
                'metric'           : self.metric + 1,
                'tx_queue_len'     : self.ifqlen,
            }
            flags = self.readableFlags(self.flags)  # NOTE: always AFTER the other calls
            r.update(flags)
            return r
    
    return Interface


class Interfaces(Collector):
    
    LINUX_SYS_INTERFACE_NAMES_DIR = u'/sys/class/net'
    
    
    def __init__(self):
        super(Interfaces, self).__init__()
        
        self._lib_interface_klass = None
    
    
    def _get_interface_klass(self):
        if self._lib_interface_klass is not None:
            return self._lib_interface_klass
        
        self._lib_interface_klass = _get_interface_klass()
        
        return self._lib_interface_klass
    
    
    def _get_all_interface_names(self):
        if os.path.exists(self.LINUX_SYS_INTERFACE_NAMES_DIR):
            _fnames = os.listdir(self.LINUX_SYS_INTERFACE_NAMES_DIR)
            return [str(fname) for fname in _fnames]  # NOT unicode, and unicode_to_bytes is NOT enough :(
        return []
    
    
    def launch(self):
        logger = self.logger
        logger.debug('getInterfaces: start')
        
        Interface_klass = self._get_interface_klass()  # lasy load
        
        if Interface_klass is None:  # like windows
            self.set_not_eligible('Your system is not managed currently.')
            return {}
        
        if not os.path.exists(self.LINUX_SYS_INTERFACE_NAMES_DIR):
            self.set_not_eligible('Your system is not managed currently.')
            return {}
        
        interface_names = self._get_all_interface_names()
        res = {}
        
        for name in interface_names:
            try:
                iface = Interface_klass(name=name)
                iface_dict = iface._iface2dict()
                entry = {
                    'loopback'         : iface_dict.get('loopback', False),
                    'up'               : iface_dict.get('up', False),
                    'mtu'              : iface_dict.get('mtu', 0),
                    'broadcast'        : iface_dict.get('broadcast', False),
                    'broadcast_address': iface_dict.get('broadcast_address', ''),
                    'ip'               : iface_dict.get('ip_address', ''),
                    'mac'              : iface_dict.get('hardware_address', ''),
                    'multicast'        : iface_dict.get('multicast', False),
                    'mask'             : iface_dict.get('net_mask', ''),
                }
                self.logger.debug('INTERFACE: %s=>%s' % (name, iface_dict))
                res[iface_dict['interface']] = entry
            
            except (OSError, IOError) as exp:
                self.logger.error('FAIL errno=%s: %s' % (exp.errno, traceback.format_exc()))
            except Exception as exp:
                self.logger.error('FAIL: %s %s' % (exp, traceback.format_exc()))
        return res
