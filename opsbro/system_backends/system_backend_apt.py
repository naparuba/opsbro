import time
import os
import subprocess

from opsbro.log import LoggerFactory

# Global logger for this part
logger = LoggerFactory.create_logger('system-packages')


class AptBackend(object):
    def __init__(self):
        self.deb_cache = None
        self.deb_cache_update_time = 0
        self.DEB_CACHE_MAX_AGE = 60  # if we cannot look at dpkg data age, allow a max cache of 60s to get a new apt update from disk
        self.DPKG_CACHE_PATH = '/var/cache/apt/pkgcache.bin'
        self.dpkg_cache_last_modification_epoch = 0.0
        
        self.need_reload = True
        
        # query cache, invalidate as soon as the apt cache is gone too
        self.has_cache = {}
        
        try:
            import apt
        except ImportError:
            apt = None
        self.apt = apt
    
    
    # Maybe the apt module is not present, if so, fix it
    def _assert_apt(self):
        if self.apt is None:
            try:
                self.install_package('python-apt')
                import apt
                self.apt = apt
            except Exception, exp:
                logger.error('Cannot install APT python lib: %s' % exp)
                return
    
    
    def has_package(self, package):
        self._assert_apt()
        if self.apt is None:
            return False
        t0 = time.time()
        if not self.deb_cache:
            self.deb_cache = self.apt.Cache()
            self.deb_cache_update_time = int(time.time())
            self.has_cache = {}
            # Cache is now load
            self.need_reload = False
        else:  # ok already existing, look if we should update it
            # because if there was a package installed, it's no more in cache
            if os.path.exists(self.DPKG_CACHE_PATH):
                last_change = os.stat(self.DPKG_CACHE_PATH).st_mtime
                if last_change != self.dpkg_cache_last_modification_epoch:
                    self.need_reload = True
                    self.dpkg_cache_last_modification_epoch = last_change
            else:  # ok we cannot look at the dpkg file age, must limit by time
                # the cache is just a memory view, so if too old, need to udpate it
                if self.deb_cache_update_time < time.time() - self.DEB_CACHE_MAX_AGE:
                    self.need_reload = True
            # Maybe the cache (in memory) was invalided
            if self.need_reload:
                self.deb_cache.open(None)
                self.deb_cache_update_time = int(time.time())
                self.has_cache = {}
                self.need_reload = False
        b = self.has_cache.get(package, None)
        if b is None:
            b = (package in self.deb_cache and self.deb_cache[package].is_installed)
            logger.debug('APT: cache miss. time to query apt for package %s: %.3f' % (package, time.time() - t0))
        return b
    
    
    # apt-get -q --yes --no-install-recommends install XXXXX
    def install_package(self, package):
        logger.debug('APT :: installing package: %s' % package)
        p = subprocess.Popen(['apt-get', 'update'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        logger.debug('APT (apt-get update):: stdout/stderr: %s/%s' % (stdout, stderr))
        if p.returncode != 0:
            raise Exception('APT: apt-get update did not succeed (%s), exiting from package installation (%s)' % (stdout + stderr, package))
        p = subprocess.Popen(['apt-get', '-q', '--yes', '--no-install-recommends', 'install', r'%s' % package], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        logger.debug('APT (apt-get install) (%s):: stdout/stderr: %s/%s' % (package, stdout, stderr))
        if p.returncode != 0:
            raise Exception('APT: apt-get install did not succeed (%s), exiting from package installation (%s)' % (stdout + stderr, package))
        # we did install a package, so our internal cache is wrong
        self.need_reload = True
        return
    
    
    # apt-get -q --yes --no-install-recommends upgrade XXXXX
    def update_package(self, package):
        logger.debug('APT :: updating package: %s' % package)
        p = subprocess.Popen(['apt-get', 'update'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        logger.debug('APT (apt-get update):: stdout/stderr: %s/%s' % (stdout, stderr))
        if p.returncode != 0:
            raise Exception('APT: apt-get update did not succeed (%s), exiting from package installation (%s)' % (stdout + stderr, package))
        p = subprocess.Popen(['apt-get', '-q', '--yes', '--no-install-recommends', 'upgrade', r'%s' % package], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        logger.debug('APT (apt-get update) (%s):: stdout/stderr: %s/%s' % (package, stdout, stderr))
        if p.returncode != 0:
            raise Exception('APT: apt-get update did not succeed (%s), exiting from package installation (%s)' % (stdout + stderr, package))
        # we did install a package, so our internal cache is wrong
        self.need_reload = True
        return
