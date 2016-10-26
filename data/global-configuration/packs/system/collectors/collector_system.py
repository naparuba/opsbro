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

class System(Collector):
    def launch(self):
        logger.debug('getSystem: start')
        res = {}
        
        res['hostname'] = platform.node()
        res['fqdn'] = socket.getfqdn()
        
        res['os'] = {}
        res['os']['name'] = os.name
        res['os']['platform'] = sys.platform
        res['architecture'] = platform.uname()[-1]
        
        res['cpucount'] = multiprocessing.cpu_count()
        
        res['linux'] = {'distname': '', 'version': '', 'id': ''}
        (distname, version, _id) = platform.linux_distribution()
        res['linux']['distname'] = distname
        res['linux']['version'] = version
        res['linux']['id'] = _id

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
