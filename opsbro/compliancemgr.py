import time
import os
import json
import glob
import imp

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


# Base class for hosting driver. MUST be used
class InterfaceComplianceDriver(object):
    name = '__MISSING__NAME__'
    
    class __metaclass__(type):
        __inheritors__ = set()
        
        
        def __new__(meta, name, bases, dct):
            klass = type.__new__(meta, name, bases, dct)
            # When creating the class, we need to look at the module where it is. It will be create like this (in collectormanager)
            # collector___global___windows___collector_iis ==> level=global  pack_name=windows, collector_name=collector_iis
            from_module = dct['__module__']
            elts = from_module.split('___')
            # Note: the master class ComplianceDriver will go in this too, but its module won't match the ___ filter
            if len(elts) != 1:
                # Let the klass know it
                klass.pack_level = elts[1]
                klass.pack_name = elts[2]
            
            meta.__inheritors__.add(klass)
            return klass
    
    @classmethod
    def get_sub_class(cls):
        return cls.__inheritors__
    
    
    def __init__(self):
        self.logger = logger
    
    
    def launch(self, rule, parameters, mode):
        rule.add_error('The driver %s is missing launch action.' % self.__class__)


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


class ComplianceManager(object):
    def __init__(self):
        self.compliances = {}
        self.did_run = False
        self.drivers = {}
    
    
    def load_backends(self):
        # First get all Hosting driver class available
        clss = InterfaceComplianceDriver.get_sub_class()
        
        for cls in clss:
            # skip base module Collector
            if cls == InterfaceComplianceDriver:
                continue
            
            ctx = cls()
            logger.debug('Trying compliance driver %s' % ctx.name)
            self.drivers[cls.name] = ctx
    
    
    def load_directory(self, directory, pack_name='', pack_level=''):
        logger.debug('Loading compliance driver directory at %s for pack %s' % (directory, pack_name))
        pth = directory + '/compliancebackend_*.py'
        collector_files = glob.glob(pth)
        for f in collector_files:
            fname = os.path.splitext(os.path.basename(f))[0]
            logger.debug('Loading compliance driver from file %s' % f)
            try:
                # NOTE: KEEP THE ___ as they are used to let the class INSIDE te module in which pack/level they are. If you have
                # another way to give the information to the inner class inside, I take it ^^
                m = imp.load_source('compliancebackend___%s___%s___%s' % (pack_level, pack_name, fname), f)
                logger.debug('Compliance driver module loaded: %s' % m)
            except Exception, exp:
                logger.error('Cannot load compliance driver %s: %s' % (fname, exp))
    
    
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
            name = compliance['display_name']
            try:
                r = evaluater.eval_expr(verify_if)
                if not r:
                    continue
            except Exception, exp:
                logger.error(' (%s) if rule (%s) evaluation did fail: %s' % (name, verify_if, exp))
                continue
            if rule is None:
                logger.error(' The compliance (%s) do not have rule' % (name))
                continue
            
            # Reset previous errors
            rule.reset()
            logger.debug('Execute compliance rule: %s' % rule)
            _type = rule.rule.get('type', '')
            
            drv = self.drivers.get(_type)
            if drv is None:
                logger.error('Cannot execute rule (%s) as the type is unknown: %s' % (name, _type))
                continue
            parameters = rule.rule.get('parameters', {})
            drv.launch(rule, parameters, mode)
    
    
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
