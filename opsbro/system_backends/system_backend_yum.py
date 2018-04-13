import subprocess
import threading

from opsbro.log import LoggerFactory

# Global logger for this part
logger = LoggerFactory.create_logger('system-packages')


class YumBackend(object):
    def __init__(self):
        self.yumbase_lock = threading.RLock()
        
        try:
            import yum
        except ImportError:
            yum = None
        self.yum = yum
    
    
    def has_package(self, package):
        # Yum conf seem to be global and so cannot set it in 2 threads at the same time
        # NOTE: the yum base is not able to detect that the cache is wrong :'(
        with self.yumbase_lock:
            return package in (pkg.name for pkg in self.yum.YumBase().rpmdb.returnPackages())
    
    
    # yum  --nogpgcheck  -y  --rpmverbosity=error  --errorlevel=1  --color=auto  install  XXXXX
    @staticmethod
    def install_package(package):
        logger.debug('YUM :: installing package: %s' % package)
        p = subprocess.Popen(['yum', '--nogpgcheck', '-y', '--rpmverbosity=error', '--errorlevel=1', '--color=auto', 'install', package], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        logger.debug('YUM (%s):: stdout: %s' % (package, stdout))
        logger.debug('YUM (%s):: stderr: %s' % (package, stderr))
        if p.returncode != 0:
            raise Exception('YUM: Cannot install package: %s from yum: %s' % (package, stdout + stderr))
        return
    
    
    # yum  --nogpgcheck  -y  --rpmverbosity=error  --errorlevel=1  --color=auto  install  XXXXX
    @staticmethod
    def update_package(package):
        logger.debug('YUM :: update package: %s' % package)
        p = subprocess.Popen(['yum', '--nogpgcheck', '-y', '--rpmverbosity=error', '--errorlevel=1', '--color=auto', 'update', package], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        logger.debug('YUM (%s):: stdout: %s' % (package, stdout))
        logger.debug('YUM (%s):: stderr: %s' % (package, stderr))
        if p.returncode != 0:
            raise Exception('YUM: Cannot update package: %s from yum: %s' % (package, stdout + stderr))
        return
