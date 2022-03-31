import subprocess
import threading
import logging
import os

from ..log import LoggerFactory
from ..util import bytes_to_unicode, PY3

from .linux_system_backend import LinuxBackend
from ..systempacketmanager_errors import InstallationFailedException, UpdateFailedException, AssertKeyFailedException, AssertRepositoryFailedException

# Global logger for this part
logger = LoggerFactory.create_logger('system-packages')


class YumBackend(LinuxBackend):
    RPM_PACKAGE_FILE_PATH = '/var/lib/rpm/Packages'  # seems to be list of installed packages
    RPM_PACKAGE_FILE_PATH_FED33 = '/var/lib/rpm/rpmdb.sqlite'  # after Fedora 33, this is the new file
    RPM_PACKAGE_FILE_PATH_FED36 = '/usr/lib/sysimage/rpm/rpmdb.sqlite' # after Fedora 36, this is the new file
    
    def __init__(self):
        self.yumbase_lock = threading.RLock()
        
        # we want to silent verbose plugins
        yum_logger = logging.getLogger("yum.verbose.YumPlugins")
        yum_logger.setLevel(logging.CRITICAL)
        self.rpm = None
        
        self._try_to_import_lib(allow_logs=False)
        
        self._installed_packages_cache = set()
        self._rpm_package_file_age = None
    
    
    def _try_to_import_lib(self, allow_logs=True):
        if self.rpm is not None:  # already done
            return
        try:
            import rpm
        except ImportError as exp:
            if allow_logs:  # when initialized, don't log
                logger.warning('Cannot import RPM librairy, package detection will be slow: %s' % exp)
            rpm = None
        self.rpm = rpm
    
    
    def _get_rpm_package_file_path(self):
        if os.path.exists(self.RPM_PACKAGE_FILE_PATH):
            return self.RPM_PACKAGE_FILE_PATH
        if os.path.exists(self.RPM_PACKAGE_FILE_PATH_FED33):
            return self.RPM_PACKAGE_FILE_PATH_FED33
        if os.path.exists(self.RPM_PACKAGE_FILE_PATH_FED36):
            return self.RPM_PACKAGE_FILE_PATH_FED36
        raise Exception('Cannot find any rpm package file on the system')
    
    
    def _assert_valid_cache(self):
        rpm_package_file = self._get_rpm_package_file_path()
        last_package_change = os.stat(rpm_package_file).st_mtime
        logger.debug('Yum:: Current rpm cache file %s, new rpm cache file: %s' % (self._rpm_package_file_age, last_package_change))
        if self._rpm_package_file_age != last_package_change:
            self._rpm_package_file_age = last_package_change
            self._update_cache()
        return
    
    
    def _update_cache(self):
        self._try_to_import_lib()
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
        else:
            logger.error('Yum:: do not havethe rpm lib installed, cannot lookup for packages')
    
    
    def has_package(self, package):
        # We do not have the rpm lib, maybe we did install it,
        if self.rpm is None:
            self._try_to_import_lib()
        
        if self.rpm is None:  # still not the lib, arg
            logger.warning('The rpm librairy is missing, switching to a slower package detection method')
            args = ['rpm', '-q', package]
            p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = p.communicate()
            logger.debug('RPM -q (%s):: stdout: %s' % (package, stdout))
            logger.debug('RPM -q (%s):: stderr: %s' % (package, stderr))
            is_installed = p.returncode == 0
            logger.debug('RPM:: Is the package %s installed? => %s' % (package, is_installed))
            return is_installed
        
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
