import time
import os
import json

if os.name != 'nt':
    from pwd import getpwuid, getpwnam
    from grp import getgrgid, getgrnam
else:
    getpwuid = getgrgid = None

from opsbro.log import LoggerFactory
from opsbro.stop import stopper
from opsbro.httpdaemon import http_export, response, abort, request
from opsbro.evaluater import evaluater

# Global logger for this part
logger = LoggerFactory.create_logger('compliance')


class Rule(object):
    def __init__(self, rule):
        self.rule = rule
        self.reset()
    
    
    def reset(self):
        self.state = 'UNKNOWN'
        self.infos = []
    
    
    def add_success(self, txt):
        self.infos.append(('SUCCESS', txt))
    
    
    def add_error(self, txt):
        self.infos.append(('ERROR', txt))
    
    
    def add_fix(self, fix):
        self.infos.append(('FIX', fix))
    
    
    def set_error(self):
        self.state = 'ERROR'
    
    
    def set_compliant(self):
        self.state = 'COMPLIANT'
    
    
    def set_fixed(self):
        self.state = 'FIXED'
    
    
    def launch(self, mode):
        # Reset previous errors
        self.reset()
        logger.debug('Execute compliance rule: %s' % self.rule)
        _type = self.rule.get('type', '')
        parameters = self.rule.get('parameters', {})
        if _type == 'file-rights':
            self.do_file_rights(parameters, mode)
    
    
    # file: /etc/passwd
    # owner: root
    # group: root
    # permissions: 644
    def do_file_rights(self, parameters, mode):
        rule = parameters
        file_path = rule.get('file', '')
        owner = rule.get('owner', '')
        group = rule.get('group' '')
        permissions = rule.get('permissions', '')
        if not file_path:
            logger.error('The rule %s do not have a file_path' % rule)
            return
        if not os.path.exists(file_path):
            logger.error('The file %s do not exists' % file_path)
            return
        
        did_fixed = False
        did_error = False
        
        logger.debug('Looking at file rights %s/%s/%s/%s with mode %s' % (file_path, owner, group, permissions, mode))
        file_stat = os.stat(file_path)
        file_permissions = int(oct(file_stat.st_mode & 0777)[1:])  # => to have something like 644
        logger.debug('Comparing mode: file:%s %s rule:%s ' % (file_permissions, type(file_permissions), permissions))
        if getpwuid is None and (owner is not '' or group is not ''):
            logger.error('Cannot look at owner/group for this os')
            return
        if owner:
            file_owner = getpwuid(file_stat.st_uid).pw_name
            logger.debug('Comparing file owner: %s and rule: %s' % (file_owner, owner))
            if file_owner != owner:
                did_error = True
                err = 'The file %s owner (%s) is not what expected: %s' % (file_path, file_owner, owner)
                self.add_error(err)
                if mode == 'enforcing':
                    uid = getpwnam(owner).pw_uid
                    fix = 'Fixing owner %s into %s' % (file_owner, owner)
                    self.add_fix(fix)
                    os.chown(file_path, uid, -1)  # do not touch group here
                    did_fixed = True
        
        if group:
            file_group = getgrgid(file_stat.st_gid).gr_name
            logger.debug('Comparing file group:%s and rule: %s' % (file_group, group))
            if file_group != group:
                did_error = True
                err = 'The file %s group (%s) is not what expected: %s' % (file_path, file_group, group)
                self.add_error(err)
                if mode == 'enforcing':
                    gid = getgrnam(group).gr_gid
                    fix = 'Fixing group %s into %s' % (file_group, group)
                    self.add_fix(fix)
                    os.chown(file_path, -1, gid)  # do not touch user here
                    did_fixed = True
        
        if permissions:
            if file_permissions != permissions:
                did_error = True
                err = 'The file %s permissions (%s) are not what is expected:%s' % (file_path, file_permissions, permissions)
                self.add_error(err)
                if mode == 'enforcing':
                    fix = 'Fixing %s into %s' % (file_permissions, permissions)
                    self.add_fix(fix)
                    # transform into octal fro chmod
                    os.chmod(file_path, int(str(permissions), 8))
                    did_fixed = True
        
        if not did_error:
            self.set_compliant()
            return
        else:
            # ok we did check and there are still error? (not fixed)
            if not did_fixed:
                self.set_error()
                return
            else:
                self.set_fixed()
                return


class ComplianceManager(object):
    def __init__(self):
        self.compliances = {}
        self.did_run = False
    
    
    def import_compliance(self, compliance, full_path, file_name, mod_time=0, pack_name='', pack_level=''):
        compliance['from'] = full_path
        compliance['pack_name'] = pack_name
        compliance['pack_level'] = pack_level
        compliance['display_name'] = compliance.get('display_name', file_name)
        rule_def = compliance.get('rule', None)
        if rule_def is not None:
            compliance['rule'] = Rule(rule_def)
        else:
            compliance['rule'] = None
        compliance['mode'] = compliance.get('mode', 'audit')
        compliance['verify_if'] = compliance.get('verify_if', 'False')
        # Add it into the list
        self.compliances[full_path] = compliance
    
    
    def do_compliance_thread(self):
        while not stopper.interrupted:
            self.launch_compliances()
            self.did_run = True
            time.sleep(1)
    
    
    def launch_compliances(self):
        for (compliance_id, compliance) in self.compliances.iteritems():
            mode = compliance['mode']
            rule = compliance['rule']
            verify_if = compliance['verify_if']
            try:
                r = evaluater.eval_expr(verify_if)
                if not r:
                    continue
            except Exception, exp:
                logger.error(' (%s) if rule (%s) evaluation did fail: %s' % (compliance['display_name'], verify_if, exp))
                continue
            if rule is not None:
                rule.launch(mode)
    
    
    def export_http(self):
        @http_export('/compliance/', method='GET')
        def get_compliance():
            response.content_type = 'application/json'
            nc = {}
            for (c_id, c) in self.compliances.iteritems():
                v = {}
                fields = ['pack_name', 'pack_level', 'display_name', 'mode', 'if']
                for f in fields:
                    v[f] = c[f]
                if c['rule'] is None:
                    v['rule'] = None
                else:
                    r = c['rule']
                    v['rule'] = {'state': r.state, 'infos': r.infos}
                nc[c_id] = v
            return json.dumps(nc)


compliancemgr = ComplianceManager()
