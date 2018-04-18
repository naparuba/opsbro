import os

if os.name != 'nt':
    from pwd import getpwnam
    from grp import getgrnam
else:
    getpwnam = None

from opsbro.compliancemgr import InterfaceComplianceDriver
from opsbro.systempacketmanager import get_systepacketmgr


class SystemUserDriver(InterfaceComplianceDriver):
    name = 'system-user'
    
    
    def __init__(self):
        super(SystemUserDriver, self).__init__()
    
    
    # name = ftp
    # uid = 14
    # gid = 50
    # display_name = 'FTP User'
    # home_dir ='/var/ftp'
    # shell= /sbin/nologin
    def launch(self, rule):
        mode = rule.get_mode()
        if mode is None:
            return
        
        matching_env = rule.get_first_matching_environnement()
        if matching_env is None:
            return
        
        systepacketmgr = get_systepacketmgr()
        
        env_name = matching_env.get_name()
        parameters = matching_env.get_parameters()
        
        name = parameters.get('name', '')
        uid = parameters.get('uid', None)
        gid = parameters.get('gid', None)
        display_name = parameters.get('display_name', '')
        home_dir = parameters.get('home_dir', '')
        shell = parameters.get('shell', '')
        if not name:
            err = 'The environnement %s do not have a name' % env_name
            rule.add_error(err)
            rule.set_error()
            return
        
        # sorry, windows is currently not managed for this
        # TODO: manage it ^^
        if getpwnam is None:
            err = 'Windows is not managed for this compliance rule'
            rule.add_error(err)
            rule.set_error()
            return
        
        did_fixed = False
        did_error = False
        
        self.logger.debug('Looking at system user %s/%s/%s/%s/%s/%s with mode %s' % (name, uid, gid, display_name, home_dir, shell, mode))
        
        try:
            current_user = getpwnam(name)
        except KeyError:  # no such user
            err = 'The user %s is not defined on the system' % name
            rule.add_error(err)
            rule.set_error()
            # Try to fix it
            try:
                systepacketmgr.create_system_user(name, uid=uid, gid=gid, display_name=display_name, home_dir=home_dir, shell=shell)
                did_fixed = True
                current_user = getpwnam(name)
            except Exception, exp:
                err = 'Cannot create the user %s: %s' % (name, exp)
                rule.add_error(err)
                rule.set_error()
                return
        
        if uid is not None and current_user.pw_uid != uid:
            err = 'The user %s do not have requested uid: %s' % (name, uid)
            rule.add_error(err)
            did_error = True
        
        if gid is not None:
            _gid = gid
            # if the user did give us a group name, try to find the integer based on it
            if not gid.isdigit():
                try:
                    _gid = getgrnam('shinken').gr_gid
                except KeyError:  # no suck group
                    _gid = None
                    err = 'The group %s request by the user %s is not found, cannot check the user group' % (name, gid)
                    rule.add_error(err)
                    did_error = True
            if _gid is not None:
                if current_user.pw_gid != _gid:
                    err = 'The user %s gid %s is not the requested group: %s(gid=%s)' % (name, current_user.pw_gid, gid, _gid)
                    rule.add_error(err)
                    did_error = True
        
        if display_name and current_user.pw_gecos != display_name:
            err = 'The user %s do not have requested display name: %s' % (name, display_name)
            rule.add_error(err)
            did_error = True
        
        if home_dir and current_user.pw_dir != home_dir:
            err = 'The user %s do not have requested home directory: %s' % (name, home_dir)
            rule.add_error(err)
            did_error = True
        
        if shell and current_user.pw_shell != shell:
            err = 'The user %s do not have requested shell: %s' % (name, shell)
            rule.add_error(err)
            did_error = True
        
        # Let's try to fix it we can
        if did_error and not did_fixed and mode == 'enforcing':
            try:
                systepacketmgr.modify_system_user(name, uid=uid, gid=gid, display_name=display_name, home_dir=home_dir, shell=shell)
                did_fixed = True
            except Exception, exp:
                err = 'Cannot modify the user %s: %s' % (name, exp)
                rule.add_error(err)
                rule.set_error()
                return
        
        # already no error? is compliant, and so DON'T run commands
        if not did_error:
            comp = 'The user %s exists with the good properties' % name
            rule.add_compliance(comp)
            rule.set_compliant()
            return
        
        # Currently we are not able to fix it
        if not did_fixed:
            rule.set_error()
            return
        
        # spawn post commands if there are some
        is_ok = rule.launch_post_commands(matching_env)
        if not is_ok:
            return
        
        # If we reach this point, means we did have errors and we did fix them all
        # and commands were happy
        rule.set_fixed()
        return
