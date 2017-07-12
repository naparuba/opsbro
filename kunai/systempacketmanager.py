import time
import os
import platform

from kunai.log import LoggerFactory
# Global logger for this part
logger = LoggerFactory.create_logger('system-packages')

try:
    import apt
except ImportError:
    apt = None

try:
    import yum
except ImportError:
    yum = None


class DummyBackend(object):
    def __init__(self):
        pass
    
    
    def has_package(self, package):
        return False


class AptBackend(object):
    def __init__(self):
        self.deb_cache = None
        self.deb_cache_update_time = 0
        self.DEB_CACHE_MAX_AGE = 60  # if we cannot look at dpkg data age, allow a max cache of 60s to get a new apt update from disk
        self.DPKG_CACHE_PATH = '/var/cache/apt/pkgcache.bin'
        self.dpkg_cache_last_modification_epoch = 0.0
        # query cache, invalidate as soon as the apt cache is gone too
        self.has_cache = {}
    
    def has_package(self, package):
        t0 = time.time()
        if not self.deb_cache:
            self.deb_cache = apt.Cache()
            self.deb_cache_update_time = int(time.time())
            self.has_cache = {}
        else:  # ok already existing, look if we should update it
            # because if there was a package installed, it's no more in cache
            need_reload = False
            if os.path.exists(self.DPKG_CACHE_PATH):
                last_change = os.stat(self.DPKG_CACHE_PATH).st_mtime
                if last_change != self.dpkg_cache_last_modification_epoch:
                    need_reload = True
                    self.dpkg_cache_last_modification_epoch = last_change
            else:  # ok we cannot look at the dpkg file age, must limit by time
                # the cache is just a memory view, so if too old, need to udpate it
                if self.deb_cache_update_time < time.time() - self.DEB_CACHE_MAX_AGE:
                    need_reload = True
            if need_reload:
                self.deb_cache.open(None)
                self.deb_cache_update_time = int(time.time())
                self.has_cache = {}
        b = self.has_cache.get(package, None)
        if b is None:
            b = (package in self.deb_cache and self.deb_cache[package].is_installed)
            logger.debug('APT: cache miss. time to query apt for package %s: %.3f' % (package, time.time() - t0))
        return b


class YumBackend(object):
    def __init__(self):
        self.yumbase = None
    
    
    def has_package(self, package):
        if not self.yumbase:
            self.yumbase = yum.YumBase()
            self.yumbase.conf.cache = 1
        return package in (pkg.name for pkg in self.yumbase.rpmdb.returnPackages())


# Try to know in which system we are running (apt, yum, or other)
# if cannot find a real backend, go to dummy that cannot find or install anything
class SystemPacketMgr(object):
    def __init__(self):
        '''
        if os.name != 'nt':
            (distname, _, _) = platform.linux_distribution()
            distname = distname.lower()
        else:
            distname = 'windows'

        self.distro = 'unknown'
        '''
        

        if yum:
            self.backend = YumBackend()
        elif apt:
            self.backend = AptBackend()
        else:  # oups
            self.backend = DummyBackend()
    
    
    def has_package(self, package):
        return self.backend.has_package(package)


systepacketmgr = SystemPacketMgr()
