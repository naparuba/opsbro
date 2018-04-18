import subprocess

from ..log import LoggerFactory

# Global logger for this part
logger = LoggerFactory.create_logger('system-packages')


class LinuxBackend(object):
    def __init__(self):
        pass
    
    
    def has_package(self, package):
        return False
    
    
    def install_package(self, package):
        raise NotImplemented()
    
    
    def update_package(self, package):
        raise NotImplemented()
    
    
    def assert_repository_key(self, key, key_server, check_only):
        raise NotImplemented()
    
    
    def assert_repository(self, name, url, key_server, check_only):
        raise NotImplemented()
    
    
    # Useradd/usermod and such can take args
    def __get_user_commands_params(self, uid, gid, display_name, home_dir, shell):
        args = []
        if uid is not None:
            args.append('--uid')
            args.append('%s' % uid)
        if gid is not None and gid is not '':
            args.append('--gid')
            args.append('%s' % gid)
        if display_name:
            args.append('--comment')
            args.append(display_name)
        if home_dir:
            # NOTE: --home-dir in add, but --home in usermod...
            args.append('-d')
            args.append(home_dir)
        if shell:
            args.append('--shell')
            args.append(shell)
        return args
    
    
    def create_system_user(self, name, uid=None, gid=None, display_name=None, home_dir=None, shell=None):
        logger.info('Creating the user %s' % name)
        args = self.__get_user_commands_params(uid, gid, display_name, home_dir, shell)
        args.insert(0, 'useradd')
        args.append(name)
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            err = 'Cannot create the user %s: %s' % (name, stdout + stderr)
            logger.error(err)
            raise Exception(err)
        return
    
    
    def modify_system_user(self, name, uid=None, gid=None, display_name=None, home_dir=None, shell=None):
        logger.info('Modify the user %s' % name)
        args = self.__get_user_commands_params(uid, gid, display_name, home_dir, shell)
        args.insert(0, 'usermod')
        args.append(name)
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            err = 'Cannot modify the user %s: %s' % (name, stdout + stderr)
            logger.error(err)
            raise Exception(err)
        return
