import time
import os
import subprocess
import threading

from opsbro.log import LoggerFactory

# Global logger for this part
logger = LoggerFactory.create_logger('system-packages')


class DnfBackend(object):
    def __init__(self):
        self.lock = threading.RLock()
    
    
    # DNF: know if a package is installed: dnf list installed "XXXX"
    # NOTE: XXXX is a regexp, so will match only installed, not the XXXX* ones
    # NOTE: --installed do not work for fedora 25 and below
    def has_package(self, package):
        with self.lock:
            logger.debug('DNF :: installing package: %s' % package)
            p = subprocess.Popen(['dnf', 'list', 'installed', r'%s' % package], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = p.communicate()
            logger.debug('DNF (%s):: stdout: %s' % (package, stdout))
            logger.debug('DNF (%s):: stderr: %s' % (package, stderr))
            # Return code is enouth to know that
            return (p.returncode == 0)
    
    
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
            return
    
    
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
            return
