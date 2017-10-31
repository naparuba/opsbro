import os
import sys
import platform
import socket

from opsbro.collector import Collector
from opsbro.util import get_public_address
from opsbro.systempacketmanager import get_systepacketmgr

try:
    import pwd
except ImportError:
    pwd = None

if os.name == 'nt':
    from opsbro.misc.wmi import wmiaccess


class System(Collector):
    def launch(self):
        logger = self.logger
        
        logger.debug('getSystem: start')
        res = {}
        
        res['hostname'] = platform.node()
        res['fqdn'] = socket.getfqdn()
        
        res['os'] = {}
        res['os']['name'] = platform.system().lower()
        res['os']['platform'] = sys.platform
        res['architecture'] = platform.uname()[-1]
        # Lazy load multiprocessing
        import multiprocessing
        res['cpu_count'] = multiprocessing.cpu_count()
        res['cpu_model_name'] = ''
        res['cpu_mhz'] = 0
        
        systepacketmgr = get_systepacketmgr()
        # Linux, directly ask python
        if res['os']['name'] == 'linux':
            (distname, version, _id) = systepacketmgr.get_distro()
            linux = {}
            res['os']['linux'] = linux
            linux['distribution'] = distname  # .lower()
            linux['version'] = version  # .lower()
            linux['id'] = _id  # .lower()
            # Maybe version is directly an int, get it
            _version = linux['version']
            _major = None
            _minor = None
            # something like 7.2
            if '.' in _version:
                elts = _version.split('.')  # no limit, if 8.0.1, will give 8.0
                try:
                    _major = int(elts[0])
                    _minor = int(elts[1])
                except ValueError:
                    pass
            else:
                try:
                    _major = int(_version)
                    _minor = 0
                except ValueError:
                    pass
            linux['major_version'] = _major
            linux['minor_version'] = _minor
            
            # Also get CPU info
            with open('/proc/cpuinfo', 'r') as f:
                buf = f.read()
                lines = buf.splitlines()
                for line in lines:
                    if ':' not in line:
                        continue
                    key, value = line.split(':', 1)
                    if key.startswith('model name'):
                        res['cpu_model_name'] = value.strip()
                    if key.startswith('cpu MHz'):
                        res['cpu_mhz'] = int(float(value.strip()))
        
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
            
            # Also get server roles
            win['features'] = []
            try:
                _features = wmiaccess.get_table_where('Win32_ServerFeature')
            except AttributeError:  # maybe the Win32_ServerFeature is missing
                _features = []
            for f in _features:
                win['features'].append(f.Name)
            win['features'].sort()
        
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
        if not res['publicip'] or res['publicip'].startswith('127.'):
            res['publicip'] = get_public_address()
        logger.debug('getsystem: completed, returning')
        return res
