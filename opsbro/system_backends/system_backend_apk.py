import os
import subprocess
import threading

from .linux_system_backend import LinuxBackend
from opsbro.log import LoggerFactory
from opsbro.util import bytes_to_unicode

# Global logger for this part
logger = LoggerFactory.create_logger('system-packages')


class ApkBackend(LinuxBackend):
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
                packages = [pname.strip() for pname in bytes_to_unicode(stdout).splitlines()]  # NOTE: force unicode as python3 will be bytes
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
    
    
    # Useradd and such can take args
    def __get_user_commands_params(self, uid, gid, display_name, home_dir, shell):
        args = []
        if uid is not None:
            args.append('-u')
            args.append('%s' % uid)
        if gid is not None and gid is not '':
            args.append('-G')
            args.append('%s' % gid)
        if display_name:
            args.append('-g')
            args.append(display_name)
        if home_dir:
            # NOTE: --home-dir in add, but --home in usermod...
            args.append('-h')
            args.append(home_dir)
        if shell:
            args.append('-s')
            args.append(shell)
        return args
    
    
    # NOTE: alpine is special because it use busybox and so a limited useradd
    def create_system_user(self, name, uid=None, gid=None, display_name=None, home_dir=None, shell=None):
        logger.info('Creating the user %s' % name)
        args = self.__get_user_commands_params(uid, gid, display_name, home_dir, shell)
        args.insert(0, 'adduser')
        args.append('-D')  # do not ask for password
        args.append(name)
        logger.info('Launching command: %s' % ' '.join(args))
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            err = 'Cannot create the user %s: %s' % (name, stdout + stderr)
            logger.error(err)
            raise Exception(err)
        return
    
    
    def modify_system_user(self, name, uid=None, gid=None, display_name=None, home_dir=None, shell=None):
        err = 'Alpine: the usermod command is not available on busybox'
        logger.error(err)
        raise Exception(err)
