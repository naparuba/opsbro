import subprocess
import threading
import logging
import os

from opsbro.log import LoggerFactory

from .linux_system_backend import LinuxBackend

# Global logger for this part
logger = LoggerFactory.create_logger('system-packages')


class YumBackend(LinuxBackend):
    def __init__(self):
        self.yumbase_lock = threading.RLock()
        
        try:
            import yum
            # we want to silent verbose plugins
            yum_logger = logging.getLogger("yum.verbose.YumPlugins")
            yum_logger.setLevel(logging.CRITICAL)
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
    
    
    # TODO: how to look if we already have the key?
    # Add a key
    #   rpm --import SERVER_KEY
    def assert_repository_key(self, key, key_server, check_only=True):
        p = subprocess.Popen(['rpm', '--import', key], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        logger.debug('YUM (rpm import):: stdout/stderr: %s/%s' % (stdout, stderr))
        if p.returncode != 0:
            raise Exception('YUM (rpm import) cannot import key (%s): %s' % (key, stdout + stderr))
        return True
    
    
    # Assert that the repository file is present
    # /etc/apt/sources.list.d/NAME.list
    # and with the good value
    # deb URL
    def assert_repository(self, name, url, key_server, check_only=True):
        pth = '/etc/yum.repos.d/%s.repo' % name
        
        content = '''[%s]
name=%s
baseurl=%s
gpgcheck=1
enabled=1
gpgkey=https://www.mongodb.org/static/pgp/server-3.4.asc
''' % (name, name, url,)
        
        if os.path.exists(pth):
            try:
                with open(pth, 'r') as f:
                    buf = f.read()
                if content == buf:
                    logger.debug('YUM the repository %s have the good value:%s' % (name, url))
                    return True
            except IOError, exp:
                err = 'YUM: cannot read the repository file: %s : %s' % (pth, exp)
                logger.error(err)
                raise Exception(err)
        
        # If we are just in audit, do NOT write it
        if check_only:
            return False
        
        # We rewrite it now
        try:
            with open(pth, 'w') as f:
                f.write(content)
            logger.info('YUM the repository %s been updated to:%s' % (name, url))
        except IOError, exp:
            err = 'YUM: cannot write repository content: %s: %s' % (pth, exp)
            logger.error(err)
            raise Exception(err)
        return True
