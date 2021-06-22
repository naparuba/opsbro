import os
import platform

from .log import LoggerFactory

# Global logger for this part
logger = LoggerFactory.create_logger('system-packages')

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


from .system_backends.linux_system_backend import LinuxBackend  # for unmanaged system
from .system_backends.system_backend_apt import AptBackend
from .system_backends.system_backend_apk import ApkBackend
from .system_backends.system_backend_yum import YumBackend
from .system_backends.system_backend_zypper import ZypperBackend


# Try to know in which system we are running (apt, yum, or other)
# if cannot find a real backend, go to dummy that cannot find or install anything
class SystemPacketMgr(object):
    def __init__(self):
        if os.name != 'nt':
            # python 3.8 do not have any more platform.linux_distribution :(
            if hasattr(platform, 'linux_distribution'):
                (distname, distversion, distid) = platform.linux_distribution()
                distname = distname.lower().strip()
                distversion = distversion.lower().strip()
                distid = distid.lower().strip()
            else:  # new python version, no luck.
                distname = ''
                distversion = ''
                distid = ''
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
            elif os.path.exists('/etc.defaults/VERSION'):  # synology linux
                with open('/etc.defaults/VERSION') as f:
                    inf = {}
                    for line in f:
                        k, v = line.rstrip().split("=")
                        # .strip('"') will remove if there or else do nothing
                        inf[k] = v.strip('"')
                distname = 'synology'
                distversion = inf['productversion'].lower().strip()
                distid = 'synology'
            else:
                distname = 'unknown'
                distversion = 'unknown'
        
        # Raw string is used by setup for display
        self.raw_distname = distname
        
        self.distro = distname
        self.distro_version = distversion
        self.distro_id = distid
        
        # Detect distro based on distname
        if 'debian' in distname:
            self.distro = 'debian'
            self.managed_system = True
        elif 'ubuntu' in distname:
            self.distro = 'ubuntu'
            self.managed_system = True
        elif 'centos' in distname:
            self.distro = 'centos'
            self.managed_system = True
        elif 'rocky linux' in distname:
            self.distro = 'rocky-linux'
            self.managed_system = True
        elif 'redhat' in distname or 'red hat' in distname:
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
        
        # Get the backend
        if self.distro in ['redhat', 'centos', 'rocky-linux', 'amazon-linux', 'amazon-linux2', 'oracle-linux', 'fedora']:
            self.backend = YumBackend()
        elif self.distro in ['debian', 'ubuntu']:
            self.backend = AptBackend()
        elif self.distro == 'alpine':
            self.backend = ApkBackend()
        elif self.distro == 'opensuse':
            self.backend = ZypperBackend()
        else:  # oups
            self.backend = LinuxBackend()
    
    
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
    
    
    def assert_repository_key(self, key, key_server, check_only):
        return self.backend.assert_repository_key(key, key_server, check_only=check_only)
    
    
    def assert_repository(self, name, url, key_server, check_only):
        return self.backend.assert_repository(name, url, key_server, check_only=check_only)
    
    
    def create_system_user(self, name, uid=None, gid=None, display_name=None, home_dir=None, shell=None):
        return self.backend.create_system_user(name, uid=uid, gid=gid, display_name=display_name, home_dir=home_dir, shell=shell)
    
    
    def modify_system_user(self, name, uid=None, gid=None, display_name=None, home_dir=None, shell=None):
        return self.backend.modify_system_user(name, uid=uid, gid=gid, display_name=display_name, home_dir=home_dir, shell=shell)


systepacketmgr_ = None


def get_systepacketmgr():
    global systepacketmgr_
    if systepacketmgr_ is None:
        logger.debug('Lazy creation of the systepacketmgr class')
        systepacketmgr_ = SystemPacketMgr()
    return systepacketmgr_
