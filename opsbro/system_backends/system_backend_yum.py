import subprocess
import threading
import logging
import os

from ..log import LoggerFactory
from ..util import bytes_to_unicode

from .linux_system_backend import LinuxBackend
from ..systempacketmanager_errors import InstallationFailedException, UpdateFailedException, AssertKeyFailedException, AssertRepositoryFailedException

# Global logger for this part
logger = LoggerFactory.create_logger('system-packages')


class YumBackend(LinuxBackend):
    RPM_PACKAGE_FILE_PATH = '/var/lib/rpm/Packages'  # seems to be list of installed packages
    
    
    def __init__(self):
        self.yumbase_lock = threading.RLock()
        
        try:
            import rpm
            # we want to silent verbose plugins
            yum_logger = logging.getLogger("yum.verbose.YumPlugins")
            yum_logger.setLevel(logging.CRITICAL)
        except ImportError:
            rpm = None
        self.rpm = rpm
        
        self.dnf = None
        if self.rpm is None:
            try:
                import dnf
                self.dnf = dnf
            except ImportError:
                pass
        
        self._installed_packages_cache = set()
        self._rpm_package_file_age = None
    
    
    def _assert_valid_cache(self):
        last_package_change = os.stat(self.RPM_PACKAGE_FILE_PATH).st_mtime
        logger.debug('Yum:: Current rpm cache file %s, new rpm cache file: %s' % (self._rpm_package_file_age, last_package_change))
        if self._rpm_package_file_age != last_package_change:
            self._rpm_package_file_age = last_package_change
            self._update_cache()
        return
    
    
    def _update_cache(self):
        if self.rpm:
            # NOTE: need to close yum base
            logger.info('RPM:: updating the rpm package cache')
            self._installed_packages_cache = set()
            ts = self.rpm.TransactionSet()
            mi = ts.dbMatch()
            for package in mi:
                package_provides = package.provides
                for package_name in package_provides:
                    package_name = bytes_to_unicode(package_name)  # python3 entries are bytes
                    # provides will give /bin/vi and libdw.so.1(ELFUTILS_0.127)(64bit) returns, and we don't want them
                    if '/' in package_name or '(' in package_name:
                        continue
                    self._installed_packages_cache.add(package_name)
                    
            # IMPORTANT: close the db before exiting, if not, memory leak will be present
            # old python do not have clear but clean instead
            if hasattr(ts, 'clear'):
                ts.clear()
            else:
                ts.clean()
            ts.closeDB()
        elif self.dnf:
            logger.info('Yum:: updating the rpm DNF package cache')
            base = self.dnf.Base()
            base.fill_sack()
            q = base.sack.query()
            all_installed = q.installed()
            self._installed_packages_cache = set([pkg.name for pkg in all_installed])
        else:
            logger.error('Yum:: do not have nor yum or dnf lib, cannot lookup for packages')
    
    
    def has_package(self, package):
        # Yum conf seem to be global and so cannot set it in 2 threads at the same time
        # NOTE: the yum base is not able to detect that the cache is wrong :'(
        with self.yumbase_lock:
            self._assert_valid_cache()  # be sure that the package list is up to date, iff need, reload it
            is_installed = package in self._installed_packages_cache
            logger.debug('Yum:: Is the package %s installed? => %s' % (package, is_installed))
            return is_installed
    
    
    # yum  --nogpgcheck  -y  --rpmverbosity=error  --errorlevel=1  --color=auto  install  XXXXX
    @staticmethod
    def install_package(package):
        logger.debug('YUM :: installing package: %s' % package)
        args = ['yum', '--nogpgcheck', '-y', '--rpmverbosity=error', '--errorlevel=1', '--color=auto', 'install', package]
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        logger.debug('YUM (%s):: stdout: %s' % (package, stdout))
        logger.debug('YUM (%s):: stderr: %s' % (package, stderr))
        if p.returncode != 0:
            raise InstallationFailedException('YUM: Cannot install package: %s from yum: %s=>%s' % (package, ' '.join(args), stdout + stderr))
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
            raise UpdateFailedException('YUM: Cannot update package: %s from yum: %s' % (package, stdout + stderr))
        return
    
    
    # TODO: how to look if we already have the key?
    # Add a key
    #   rpm --import SERVER_KEY
    def assert_repository_key(self, key, key_server, check_only=True):
        p = subprocess.Popen(['rpm', '--import', key], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        logger.debug('YUM (rpm import):: stdout/stderr: %s/%s' % (stdout, stderr))
        if p.returncode != 0:
            raise AssertKeyFailedException('YUM (rpm import) cannot import key (%s): %s' % (key, stdout + stderr))
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
            except IOError as exp:
                err = 'YUM: cannot read the repository file: %s : %s' % (pth, exp)
                logger.error(err)
                raise AssertRepositoryFailedException(err)
        
        # If we are just in audit, do NOT write it
        if check_only:
            return False
        
        # We rewrite it now
        try:
            with open(pth, 'w') as f:
                f.write(content)
            logger.info('YUM the repository %s been updated to:%s' % (name, url))
        except IOError as exp:
            err = 'YUM: cannot write repository content: %s: %s' % (pth, exp)
            logger.error(err)
            raise AssertRepositoryFailedException(err)
        return True
