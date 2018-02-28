import os

if os.name != 'nt':
    from pwd import getpwuid, getpwnam
    from grp import getgrgid, getgrnam
else:
    getpwuid = getgrgid = None
    
from opsbro.compliancemgr import InterfaceComplianceDriver

class FileRightsDriver(InterfaceComplianceDriver):
    name = 'file-rights'
    
    def __init__(self):
        super(FileRightsDriver, self).__init__()


    # file: /etc/passwd
    # owner: root
    # group: root
    # permissions: 644
    def launch(self, rule, parameters, mode):
        file_path = parameters.get('file', '')
        owner = parameters.get('owner', '')
        group = parameters.get('group' '')
        permissions = parameters.get('permissions', '')
        if not file_path:
            self.logger.error('The rule %s do not have a file_path' % parameters)
            return
        if not os.path.exists(file_path):
            self.logger.error('The file %s do not exists' % file_path)
            return
    
        did_fixed = False
        did_error = False

        self.logger.debug('Looking at file rights %s/%s/%s/%s with mode %s' % (file_path, owner, group, permissions, mode))
        file_stat = os.stat(file_path)
        file_permissions = int(oct(file_stat.st_mode & 0777)[1:])  # => to have something like 644
        self.logger.debug('Comparing mode: file:%s %s rule:%s ' % (file_permissions, type(file_permissions), permissions))
        if getpwuid is None and (owner is not '' or group is not ''):
            self.logger.error('Cannot look at owner/group for this os')
            return
        if owner:
            file_owner = getpwuid(file_stat.st_uid).pw_name
            self.logger.debug('Comparing file owner: %s and rule: %s' % (file_owner, owner))
            if file_owner != owner:
                did_error = True
                err = 'The file %s owner (%s) is not what expected: %s' % (file_path, file_owner, owner)
                rule.add_error(err)
                if mode == 'enforcing':
                    uid = getpwnam(owner).pw_uid
                    fix = 'Fixing owner %s into %s' % (file_owner, owner)
                    rule.add_fix(fix)
                    os.chown(file_path, uid, -1)  # do not touch group here
                    did_fixed = True
    
        if group:
            file_group = getgrgid(file_stat.st_gid).gr_name
            self.logger.debug('Comparing file group:%s and rule: %s' % (file_group, group))
            if file_group != group:
                did_error = True
                err = 'The file %s group (%s) is not what expected: %s' % (file_path, file_group, group)
                rule.add_error(err)
                if mode == 'enforcing':
                    gid = getgrnam(group).gr_gid
                    fix = 'Fixing group %s into %s' % (file_group, group)
                    rule.add_fix(fix)
                    os.chown(file_path, -1, gid)  # do not touch user here
                    did_fixed = True
    
        if permissions:
            if file_permissions != permissions:
                did_error = True
                err = 'The file %s permissions (%s) are not what is expected:%s' % (file_path, file_permissions, permissions)
                rule.add_error(err)
                if mode == 'enforcing':
                    fix = 'Fixing %s into %s' % (file_permissions, permissions)
                    rule.add_fix(fix)
                    # transform into octal fro chmod
                    os.chmod(file_path, int(str(permissions), 8))
                    did_fixed = True
    
        if not did_error:
            rule.set_compliant()
            return
        else:
            # ok we did check and there are still error? (not fixed)
            if not did_fixed:
                rule.set_error()
                return
            else:
                rule.set_fixed()
                return
