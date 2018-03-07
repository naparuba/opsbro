import subprocess
import threading

from opsbro.log import LoggerFactory

# Global logger for this part
logger = LoggerFactory.create_logger('system-packages')


class ZypperBackend(object):
    def __init__(self):
        self.lock = threading.RLock()
    
    
    # rpm -q -a --queryformat "%{NAME}\n"
    def has_package(self, package):
        with self.lock:
            logger.debug('ZYPPER :: has package: %s' % package)
            p = subprocess.Popen(['rpm', '-q', '-a', '--queryformat', r'"%{NAME}\n"'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = p.communicate()
            # Return code is enouth to know that
            if p.returncode != 0:
                raise Exception('ZYPPER: Cannot list pacakge' % (stdout + stderr))
            return package in stdout.splitlines()
    
    
    # zypper --non-interactive install  XXXXX
    def install_package(self, package):
        with self.lock:
            logger.debug('ZYPPER :: installing package: %s' % package)
            p = subprocess.Popen(['zypper', '--non-interactive', 'install', r'%s' % package], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = p.communicate()
            logger.debug('ZYPPER (%s):: stdout: %s' % (package, stdout))
            logger.debug('ZYPPER (%s):: stderr: %s' % (package, stderr))
            if p.returncode != 0:
                raise Exception('ZYPPER: Cannot install package: %s from zypper: %s' % (package, stdout + stderr))
            return
    
    
    # zypper --non-interactive update  XXXXX
    def update_package(self, package):
        with self.lock:
            logger.debug('ZYPPER :: installing package: %s' % package)
            p = subprocess.Popen(['zypper', '--non-interactive', 'update', r'%s' % package], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = p.communicate()
            logger.debug('ZYPPER (%s):: stdout: %s' % (package, stdout))
            logger.debug('ZYPPER (%s):: stderr: %s' % (package, stderr))
            if p.returncode != 0:
                raise Exception('ZYPPER: Cannot update package: %s from zypper: %s' % (package, stdout + stderr))
            return
