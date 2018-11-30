import subprocess
import threading
import os

from .linux_system_backend import LinuxBackend
from opsbro.log import LoggerFactory

# Global logger for this part
logger = LoggerFactory.create_logger('system-packages')


class DnfBackend(LinuxBackend):
    RPM_PACKAGE_FILE_PATH = '/var/lib/rpm/Packages'  # seems to be list of installed packages
    
    
    def __init__(self):
        self.lock = threading.RLock()
        
        self._installed_packages_cache = {}  # only tested packages will be kepts, and reset if yum/rpm installs
        self._rpm_package_file_age = None
    
    
    def _assert_valid_cache(self):
        last_package_change = os.stat(self.RPM_PACKAGE_FILE_PATH).st_mtime
        
        if self._rpm_package_file_age != last_package_change:
            self._rpm_package_file_age = last_package_change
            self._installed_packages_cache.clear()
    
    
    # DNF: know if a package is installed: dnf list installed "XXXX"
    # NOTE: XXXX is a regexp, so will match only installed, not the XXXX* ones
    # NOTE: --installed do not work for fedora 25 and below
    def has_package(self, package):
        with self.lock:
            # If the rpm base did move, reset the cache
            self._assert_valid_cache()
            
            if package in self._installed_packages_cache:
                return self._installed_packages_cache[package]
            
            logger.debug('DNF :: installing package: %s' % package)
            p = subprocess.Popen(['dnf', 'list', 'installed', r'%s' % package], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = p.communicate()
            logger.debug('DNF (%s):: stdout: %s' % (package, stdout))
            logger.debug('DNF (%s):: stderr: %s' % (package, stderr))
            # Return code is enouth to know that
            is_installed = (p.returncode == 0)
            
            # Update cache
            self._installed_packages_cache[package] = is_installed
            
            return is_installed
    
    
    # yum  --nogpgcheck  -y  --rpmverbosity=error  --errorlevel=1  --color=auto  install  XXXXX
    def install_package(self, package):
        with self.lock:
            logger.debug('DNF :: installing package: %s' % package)
            p = subprocess.Popen(['dnf', '--nogpgcheck', '-y', '--rpmverbosity=error', '--errorlevel=1', '--color=auto', 'install', r'%s' % package], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = p.communicate()
            logger.debug('DNF (%s):: stdout: %s' % (package, stdout))
            logger.debug('DNF (%s):: stderr: %s' % (package, stderr))
            if p.returncode != 0:
                raise Exception('DNF: Cannot install package: %s from dnf: %s' % (package, stdout + stderr))
            # NOTE: cache will be reset when go into the has_pacakge
    
    
    def update_package(self, package):
        # update
        with self.lock:
            logger.debug('DNF :: updating package: %s' % package)
            p = subprocess.Popen(['dnf', '--nogpgcheck', '-y', '--rpmverbosity=error', '--errorlevel=1', '--color=auto', 'update', r'%s' % package], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = p.communicate()
            logger.debug('DNF (%s):: stdout: %s' % (package, stdout))
            logger.debug('DNF (%s):: stderr: %s' % (package, stderr))
            if p.returncode != 0:
                raise Exception('DNF: Cannot update package: %s from dnf: %s' % (package, stdout + stderr))
            # NOTE: cache will be reset when go into the has_pacakge
