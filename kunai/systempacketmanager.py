import time
import os
import platform
import subprocess
import threading

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
    
    
    def install_package(self, package):
        raise NotImplemented()


class AptBackend(object):
    def __init__(self):
        self.deb_cache = None
        self.deb_cache_update_time = 0
        self.DEB_CACHE_MAX_AGE = 60  # if we cannot look at dpkg data age, allow a max cache of 60s to get a new apt update from disk
        self.DPKG_CACHE_PATH = '/var/cache/apt/pkgcache.bin'
        self.dpkg_cache_last_modification_epoch = 0.0
        # query cache, invalidate as soon as the apt cache is gone too
        self.has_cache = {}

    # Maybe the apt module is not present, if so, fix it
    def assert_apt(self):
        global apt
        if apt is None:
            try:
                self.install_package('python-apt')
                import apt
            except Exception, exp:
                logger.error('Cannot install APT python lib: %s' % exp)
                return
    
    
    def has_package(self, package):
        self.assert_apt()
        if apt is None:
            return False
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
    
    
    # apt-get -q --yes --no-install-recommends install XXXXX
    @staticmethod
    def install_package(package):
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
        return


class YumBackend(object):
    def __init__(self):
        self.yumbase = None
        self.yumbase_lock = threading.RLock()
    
    
    def has_package(self, package):
        # Yum conf seem to be global and so cannot set it in 2 threads at the same time
        with self.yumbase_lock:
            if not self.yumbase:
                self.yumbase = yum.YumBase()
                self.yumbase.conf.cache = 1
        return package in (pkg.name for pkg in self.yumbase.rpmdb.returnPackages())
    
    
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


# Try to know in which system we are running (apt, yum, or other)
# if cannot find a real backend, go to dummy that cannot find or install anything
class SystemPacketMgr(object):
    def __init__(self):
        
        if os.name != 'nt':
            (distname, distversion, _) = platform.linux_distribution()
            distname = distname.lower()
        else:
            distname = 'windows'
            distversion = ''
        
        # Maybe linux_distribution did give us bull shit, so try other files like
        # os-release
        if distname == '':
            if os.path.exists('/etc/os-release'):
                with open('/etc/os-release') as f:
                    inf = {}
                    for line in f:
                        k, v = line.rstrip().split("=")
                        # .strip('"') will remove if there or else do nothing
                        inf[k] = v.strip('"')
                distname = inf['ID']
                distversion = inf['VERSION_ID']

        
        # Raw string is used by setup for display
        self.raw_distname = distname
        
        self.distro = ''
        self.distro_version = ''
        if 'debian' in distname:
            self.distro = 'debian'
            self.distro_version = distversion
        elif 'ubuntu' in distname:
            self.distro = 'ubuntu'
            self.distro_version = distversion
        elif 'centos' in distname:
            self.distro = 'centos'
            self.distro_version = distversion
        elif 'redhat' in distname:
            self.distro = 'redhat'
            self.distro_version = distversion
        elif 'fedora' in distname:
            self.distro = 'fedora'
            self.distro_version = distversion
        elif 'oracle linux' in distname:
            self.distro = 'oracle'
            self.distro_version = distversion
        elif 'amzn' in distname:
            self.distro = 'amzn'
            self.distro_version = distversion
        elif distname == 'windows':
            self.distro = 'windows'
            self.distro_version = distversion
        else:
            self.distro = ''
            self.distro_version = ''
        
            

        if self.distro in ['redhat', 'centos', 'amzn', 'oracle']:
            if yum is not None:
                self.backend = YumBackend()
            else:
                logger.error('This is a yum based linux distribution, but the python yum librairy is missing. Please install it to enable package system management.')
                self.backend = DummyBackend()
        elif self.distro in ['debian', 'ubuntu']:
            self.backend = AptBackend()
        elif self.distro == 'fedora':
            logger.error('The fedora DNF backend is not currently managed.')
            self.backend = DummyBackend()
        else:  # oups
            self.backend = DummyBackend()
    
    
    def has_package(self, package):
        return self.backend.has_package(package)
    
    
    def get_distro(self):
        return self.distro, self.distro_version
    
    
    def get_raw_distro(self):
        return self.raw_distname
    
    def install_package(self, package):
        self.backend.install_package(package)


systepacketmgr = SystemPacketMgr()
