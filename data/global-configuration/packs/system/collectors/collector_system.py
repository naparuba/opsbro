import os
import sys
import platform
import multiprocessing
import socket
from kunai.log import logger
from kunai.collector import Collector
from kunai.util import get_public_address

try:
    import pwd
except ImportError:
    pwd = None


if os.name == 'nt':
    from kunai.misc.wmi import wmiaccess

    
class System(Collector):
    def launch(self):
        logger.debug('getSystem: start')
        res = {}
        
        res['hostname'] = platform.node()
        res['fqdn'] = socket.getfqdn()

        res['os'] = {}
        res['os']['name'] = platform.system().lower()
        res['os']['platform'] = sys.platform
        res['architecture'] = platform.uname()[-1]
        
        res['cpucount'] = multiprocessing.cpu_count()
        
        # Linux, directly ask python
        if os.name == 'linux2':
            res['linux'] = {'distname': '', 'version': '', 'id': ''}
            (distname, version, _id) = platform.linux_distribution()
            res['linux']['distname'] = distname
            res['linux']['version'] = version
            res['linux']['id'] = _id

        # Windows, get data from Win32_OperatingSystem
        if os.name == 'nt':
            win = {}
            res['windows'] = win
            _os = wmiaccess.get_table_where('Win32_OperatingSystem', {'Primary': 1})
            # only the first entry
            _os = _os[0]
            props = ['Caption', 'ServicePackMajorVersion', 'ServicePackMinorVersion',
                     'SerialNumber', 'OSArchitecture', 'MUILanguages', 'CSDVersion']
            for prop in props:
                win[prop.lower()] = getattr(_os, prop)

        if hasattr(os, 'getlogin'):
            try:
                res['user'] = os.getlogin()
            except OSError:  # some background daemon can have problem on ancien os
                if pwd is not None:
                    res['user'] = pwd.getpwuid(os.geteuid()).pw_name
            res['uid'] = os.getuid()
            res['gid'] = os.getgid()

        res['publicip'] = ''
        try:
            res['publicip'] = socket.gethostbyname(socket.gethostname())
        except socket.gaierror:
            pass
        if not res['publicip'] or res['publicip'] == '127.0.0.1':
            res['publicip'] = get_public_address()
        logger.debug('getsystem: completed, returning')
        return res
