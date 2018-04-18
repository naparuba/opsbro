import time
import os
import subprocess
import threading

from opsbro.log import LoggerFactory
from .linux_system_backend import LinuxBackend

# Global logger for this part
logger = LoggerFactory.create_logger('system-packages')


class AptBackend(LinuxBackend):
    def __init__(self):
        self.deb_cache = None
        self.deb_cache_update_time = 0
        self.DEB_CACHE_MAX_AGE = 5  # if we cannot look at dpkg data age, allow a max cache of 60s to get a new apt update from disk
        self.DPKG_CACHE_PATH = '/var/cache/apt/pkgcache.bin'
        self.dpkg_cache_last_modification_epoch = 0.0
        
        self.gpg_cache_lock = threading.RLock()
        self.gpg_cache_path = '/etc/apt/trusted.gpg'
        self.gpg_cache_last_modification_date = 0
        self.gpg_cache = {}
        
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
    
    
    # Check if a key is there
    #   apt-key export KEY | grep 'BEGIN PGP PUBLIC KEY BLOCK'
    # Add a key
    #   apt-key adv --keyserver hkp://KEY_SERVER --recv KEY
    def assert_repository_key(self, key, key_server, check_only=True):
        # Maybe the key is already there in cache
        # and the cache is still valid
        
        with self.gpg_cache_lock:
            if os.path.exists(self.gpg_cache_path):
                # If the gpg key did change, reset the cache
                last_change = os.stat(self.gpg_cache_path).st_mtime
                if last_change != self.gpg_cache_last_modification_date:
                    self.gpg_cache.clear()
                    self.gpg_cache_last_modification_date = last_change
            else:
                # clean the cache, always so we for a full recheck
                self.gpg_cache.clear()
            presence = self.gpg_cache.get(key, None)
            if presence is True:
                logger.debug('APT: apt-key list already have key %s' % key)
                return True
        
        p = subprocess.Popen(['apt-key', 'export', key], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        logger.info('APT (apt-key listing):: stdout/stderr: %s/%s' % (stdout, stderr))
        lines = stdout.splitlines()
        for line in lines:
            if "BEGIN PGP PUBLIC KEY BLOCK" in line:
                logger.debug('APT: apt-key list already have key %s' % key)
                # Update the cache
                with self.gpg_cache_lock:
                    self.gpg_cache[key] = True
                return True
        
        # If we just want to check only, do not import the key
        if check_only:
            return False
        
        # Ok do not have the key, add it
        logger.info('APT :: updating repository key %s from key server: %s' % (key, key_server))
        if not key_server.startswith('hkp://'):
            key_server = 'hkp://%s' % key_server
        p = subprocess.Popen(['apt-key', 'adv', '--keyserver', key_server, '--recv', key], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        logger.info('APT (apt-key adv):: stdout/stderr: %s/%s' % (stdout, stderr))
        if p.returncode != 0:
            raise Exception('APT: apt-key adv update did not succeed (%s), exiting from serveur key update' % (stdout + stderr))
        with self.gpg_cache_lock:
            self.gpg_cache[key] = True
        return True
    
    
    # Assert that the repository file is present
    # /etc/apt/sources.list.d/NAME.list
    # and with the good value
    # deb URL
    def assert_repository(self, name, url, key_server, check_only=True):
        pth = '/etc/apt/sources.list.d/%s.list' % name
        
        content = 'deb %s\n' % url
        
        if os.path.exists(pth):
            try:
                with open(pth, 'r') as f:
                    buf = f.read()
                if content == buf:
                    logger.debug('APT the repository %s have the good value:%s' % (name, url))
                    return True
            except IOError, exp:
                err = 'APT: cannot read the repository file: %s : %s' % (pth, exp)
                logger.error(err)
                raise Exception(err)
        
        # If we are just in audit, do NOT write it
        if check_only:
            return False
        
        # We rewrite it now
        try:
            with open(pth, 'w') as f:
                f.write(content)
            logger.info('APT the repository %s been updated to:%s' % (name, url))
        except IOError, exp:
            err = 'APT: cannot write repository content: %s: %s' % (pth, exp)
            logger.error(err)
            raise Exception(err)
        return True
