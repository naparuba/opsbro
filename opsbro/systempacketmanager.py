import time
import os
import platform
import subprocess
import threading

from opsbro.log import LoggerFactory

# Global logger for this part
logger = LoggerFactory.create_logger('system-packages')


class DummyBackend(object):
    def __init__(self):
        pass
    
    
    def has_package(self, package):
        return False
    
    
    def install_package(self, package):
        raise NotImplemented()
    
    
    def update_package(self, package):
        raise NotImplemented()


# TODO: get a way to know if a service is enabled, or not
# RUN level: [root@centos-7 ~]# systemctl get-default
# multi-user.target   ==> 3
# graphical.target    ==> 5
# systemctl list-unit-files --full --type=service --state=enabled --plain --no-legend
# &
# chkconfig --list 2>/dev/null| grep '3:on'

# DEBIAN:
# Run level:
# root@docker-host:~/opsbro-oss# systemctl get-default
# graphical.target


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


class ApkBackend(object):
    def __init__(self):
        self.apk_installed_packages = set()
        self.apk_cache_time = 0.0
        self.apk_cache_lock = threading.RLock()
        self.APK_CACHE_FILE = "/lib/apk/db/installed"
    
    
    # APK can give us installed packages with apk info.
    # and the cache is the file /lib/apk/db/installed
    def _update_apk_cache(self):
        with self.apk_cache_lock:
            need_reload = False
            # If the cache file did change, we need to reload all
            # If it do not exists, then my apk driver is bad on a alpine version, please fill
            # a bug ^^
            if os.path.exists(self.APK_CACHE_FILE):
                last_change = os.stat(self.APK_CACHE_FILE).st_mtime
                if last_change != self.apk_cache_time:
                    need_reload = True
                    self.apk_cache_time = last_change
            else:
                need_reload = True
            
            if need_reload:
                p = subprocess.Popen(['apk', 'info'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = p.communicate()
                logger.debug('APK (apk info) :: stdout/stderr: %s/%s' % (stdout, stderr))
                if p.returncode != 0:
                    raise Exception('APK: apk info id not succeed (%s), exiting from package listing' % (stdout + stderr))
                packages = [pname.strip() for pname in stdout.splitlines()]
                self.apk_installed_packages = set(packages)
                return
    
    
    def has_package(self, package):
        # Be sure the apk cache is up to date
        self._update_apk_cache()
        b = (package in self.apk_installed_packages)
        logger.debug('APK: (apk info) is package %s installed: %s' % (package, b))
        return b
    
    
    # apk --no-progress --allow-untrusted --update-cache add XXXXX
    # --no-progress: no progress bar
    # --allow-untrusted: do not need to validate the repos
    # --update-cache: thanks! at least it can update before install
    @staticmethod
    def install_package(package):
        logger.debug('APK :: installing package: %s' % package)
        p = subprocess.Popen(['apk', '--no-progress', '--allow-untrusted', '--update-cache', 'add', r'%s' % package], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        logger.debug('APK (apk add) (%s):: stdout/stderr: %s/%s' % (package, stdout, stderr))
        if p.returncode != 0:
            raise Exception('APK: apk add id not succeed (%s), exiting from package installation (%s)' % (stdout + stderr, package))
        return
    
    
    # apk --no-progress --allow-untrusted --update-cache --upgrade add XXXXX
    # --no-progress: no progress bar
    # --allow-untrusted: do not need to validate the repos
    # --update-cache: thanks! at least it can update before install
    # --upgrade => allow update of a package
    @staticmethod
    def update_package(package):
        logger.debug('APK :: updating package: %s' % package)
        p = subprocess.Popen(['apk', '--no-progress', '--allow-untrusted', '--update-cache', 'add', '--upgrade', r'%s' % package], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        logger.debug('APK (apk update) (%s):: stdout/stderr: %s/%s' % (package, stdout, stderr))
        if p.returncode != 0:
            raise Exception('APK: apk add id not succeed (%s), exiting from package updating (%s)' % (stdout + stderr, package))
        return


from .system_backends.system_backend_apt import AptBackend
from .system_backends.system_backend_yum import YumBackend


# Try to know in which system we are running (apt, yum, or other)
# if cannot find a real backend, go to dummy that cannot find or install anything
class SystemPacketMgr(object):
    def __init__(self):
        if os.name != 'nt':
            (distname, distversion, distid) = platform.linux_distribution()
            distname = distname.lower().strip()
            distversion = distversion.lower().strip()
            distid = distid.lower().strip()
        else:
            distname = 'windows'
            distversion = ''
            distid = ''
        
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
                distname = inf['ID'].lower().strip()
                distversion = inf['VERSION_ID'].lower().strip()
                distid = inf['ID'].lower().strip()
        
        # Raw string is used by setup for display
        self.raw_distname = distname
        
        self.distro = distname
        self.distro_version = distversion
        self.distro_id = distid
        
        if 'debian' in distname:
            self.distro = 'debian'
            self.managed_system = True
        elif 'ubuntu' in distname:
            self.distro = 'ubuntu'
            self.managed_system = True
        elif 'centos' in distname:
            self.distro = 'centos'
            self.managed_system = True
        elif 'redhat' in distname:
            self.distro = 'redhat'
            self.managed_system = True
        elif 'fedora' in distname:
            self.distro = 'fedora'
            self.managed_system = True
        elif 'oracle linux' in distname:
            self.distro = 'oracle-linux'
            self.managed_system = True
        elif 'amzn' in distname:
            self.managed_system = True
            # Old version (amaonz1) start with the date
            if distversion.startswith('201'):
                self.distro = 'amazon-linux'
            else:
                self.distro = 'amazon-linux2'
        elif distname == 'windows':
            self.distro = 'windows'
            self.managed_system = True
        elif 'alpine' in distname:
            self.distro = 'alpine'
            self.managed_system = True
        elif 'opensuse' in distname:
            self.distro = 'opensuse'
            self.managed_system = True
        else:
            # ok not managed one
            self.managed_system = False
        
        if self.distro in ['redhat', 'centos', 'amazon-linux', 'amazon-linux2', 'oracle-linux']:
            #if yum is not None:
            self.backend = YumBackend()
            #else:
            #    logger.error('This is a yum based linux distribution, but the python yum librairy is missing. Please install it to enable package system management.')
            #    self.backend = DummyBackend()
        elif self.distro in ['debian', 'ubuntu']:
            self.backend = AptBackend()
        elif self.distro == 'alpine':
            self.backend = ApkBackend()
        elif self.distro == 'fedora':
            self.backend = DnfBackend()
        elif self.distro == 'opensuse':
            self.backend = ZypperBackend()
        else:  # oups
            self.backend = DummyBackend()
    
    
    def is_managed_system(self):
        return self.managed_system
    
    
    def has_package(self, package):
        return self.backend.has_package(package)
    
    
    def get_distro(self):
        return self.distro, self.distro_version, self.distro_id
    
    
    def get_raw_distro(self):
        return self.raw_distname
    
    
    def install_package(self, package):
        self.backend.install_package(package)
    
    
    def update_or_install(self, package):
        if self.backend.has_package(package):
            self.backend.update_package(package)
        else:
            self.backend.install_package(package)


systepacketmgr_ = None


def get_systepacketmgr():
    global systepacketmgr_
    if systepacketmgr_ is None:
        logger.debug('Lazy creation of the systepacketmgr class')
        systepacketmgr_ = SystemPacketMgr()
    return systepacketmgr_
