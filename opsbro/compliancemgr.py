import time
import os
import json
import glob
import imp

from .log import LoggerFactory
from .stop import stopper
from .httpdaemon import http_export, response
from .evaluater import evaluater
from .util import make_dir

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
    
    
    def launch(self, rule):
        rule.add_error('The driver %s is missing launch action.' % self.__class__)


class Rule(object):
    def __init__(self, pack_name, pack_level, name, mode, verify_if, rule_def):
        self.rule_def = rule_def
        self.type = self.rule_def.get('type')
        self.pack_name = pack_name
        self.pack_level = pack_level
        self.name = name
        self.mode = mode
        self.verify_if = verify_if
        
        self.__state = 'UNKNOWN'
        self.__old_state = 'UNKNOWN'
        self.__infos = []
        self.__did_change = False
        self.reset()
    
    
    def reset(self):
        self.__did_change = False
        self.__infos = []
    
    
    def get_mode(self):
        return self.mode
    
    
    def get_parameters(self):
        return self.rule_def.get('parameters', {})
    
    
    def get_type(self):
        return self.type
    
    
    def get_verify_if(self):
        return self.verify_if
    
    
    def get_name(self):
        return self.name
    
    
    def add_success(self, txt):
        self.__infos.append({'state': 'SUCCESS', 'text': txt})
    
    
    def add_error(self, txt):
        self.__infos.append({'state': 'ERROR', 'text': txt})
    
    
    def add_fix(self, txt):
        self.__infos.append({'state': 'FIX', 'text': txt})
    
    
    def add_compliance(self, txt):
        self.__infos.append({'state': 'COMPLIANT', 'text': txt})
    
    
    def __set_state(self, state):
        if self.__state == state:
            return
        
        self.__did_change = True
        self.__old_state = self.__state
        self.__state = state
        logger.debug('Compliance rule %s switch from %s to %s' % (self.name, self.__old_state, self.__state))
    
    
    def set_error(self):
        self.__set_state('ERROR')
    
    
    def set_compliant(self):
        self.__set_state('COMPLIANT')
    
    
    def set_fixed(self):
        self.__set_state('FIXED')
    
    
    def set_not_eligible(self):
        self.__set_state('NOT-ELIGIBLE')
    
    
    def get_json_dump(self):
        return {'name': self.name, 'state': self.__state, 'old_state': self.__old_state, 'infos': self.__infos, 'mode': self.mode, 'pack_level': self.pack_level, 'pack_name': self.pack_name, 'type': self.type}
    
    
    def get_history_entry(self):
        if not self.__did_change:
            return None
        return self.get_json_dump()


class ComplianceManager(object):
    def __init__(self):
        self.compliances = {}
        self.did_run = False
        self.drivers = {}
        
        self.history_directory = None
        self.__current_history_entry = []
    
    
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
        
        # Prepare the history
        from .configurationmanager import configmgr
        data_dir = configmgr.get_data_dir()
        self.history_directory = os.path.join(data_dir, 'compliance_history')
        logger.debug('Asserting existence of the compliance history directory: %s' % self.history_directory)
        if not os.path.exists(self.history_directory):
            make_dir(self.history_directory)
    
    
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
        name = compliance.get('name', file_name)
        mode = compliance.get('mode', 'audit')
        if mode not in ('audit', 'enforcing'):
            logger.error('The compliance definition got a wrong mode :%s' % mode)
            return
        verify_if = compliance.get('verify_if', 'False')
        
        rule_def = compliance.get('rule', None)
        if rule_def is None:
            logger.error('The compliance definition is missing a rule entry :%s' % full_path)
            return
        rule_type = rule_def.get('type')
        if not rule_type:
            logger.error('The compliance definition is missing a rule type entry :%s' % full_path)
            return
        
        rule = Rule(pack_name, pack_level, name, mode, verify_if, rule_def)
        # Add it into the list
        self.compliances[full_path] = rule
    
    
    def add_history_entry(self, history_entry):
        self.__current_history_entry.append(history_entry)
    
    
    def __write_history_entry(self):
        # Noting to do?
        if not self.__current_history_entry:
            return
        now = int(time.time())
        pth = os.path.join(self.history_directory, '%d.json' % now)
        logger.info('Saving new compliance history entry to %s' % pth)
        buf = json.dumps(self.__current_history_entry)
        with open(pth, 'w') as f:
            f.write(buf)
        # Now we can reset it
        self.__current_history_entry = []
    
    
    def launch_compliances(self):
        for (compliance_id, rule) in self.compliances.iteritems():
            verify_if = rule.get_verify_if()
            name = rule.get_name()
            try:
                r = evaluater.eval_expr(verify_if)
                if not r:
                    rule.set_not_eligible()
                    continue
            except Exception, exp:
                err = ' (%s) if rule (%s) evaluation did fail: %s' % (name, verify_if, exp)
                logger.error(err)
                rule.add_error(err)
                rule.set_error()
                continue
            
            # Reset previous errors
            rule.reset()
            logger.debug('Execute compliance rule: %s' % rule)
            _type = rule.get_type()
            
            drv = self.drivers.get(_type)
            if drv is None:
                logger.error('Cannot execute rule (%s) as the type is unknown: %s' % (name, _type))
                continue
            drv.launch(rule)
            history_entry = rule.get_history_entry()
            if history_entry:
                self.add_history_entry(history_entry)
    
    
    def get_history(self):
        r = []
        current_size = 0
        max_size = 1024 * 1024
        reg = self.history_directory + '/*.json'
        history_files = glob.glob(reg)
        # Get from the more recent to the older
        history_files.sort()
        history_files.reverse()
        
        # Do not send more than 1MB, but always a bit more, not less
        for history_file in history_files:
            epoch_time = int(os.path.splitext(os.path.basename(history_file))[0])
            with open(history_file, 'r') as f:
                e = json.loads(f.read())
            r.append({'date': epoch_time, 'entries': e})
            
            # If we are now too big, return directly
            size = os.path.getsize(history_file)
            current_size += size
            if current_size > max_size:
                # Give older first
                r.reverse()
                return r
        # give older first
        r.reverse()
        return r
    
    
    def do_compliance_thread(self):
        from .collectormanager import collectormgr
        # if the collector manager did not run, our evaluation can be invalid, so wait for all collectors to run at least once
        while collectormgr.did_run == False:
            time.sleep(0.25)
        while not stopper.interrupted:
            self.launch_compliances()
            self.did_run = True
            # For each changes, we write a history entry
            self.__write_history_entry()
            time.sleep(1)
    
    
    def export_http(self):
        @http_export('/compliance/state', method='GET')
        def get_compliance_state():
            response.content_type = 'application/json'
            nc = {}
            for (c_id, c) in self.compliances.iteritems():
                nc[c_id] = c.get_json_dump()
            return json.dumps(nc)
        
        
        @http_export('/compliance/history', method='GET')
        def get_compliance_history():
            response.content_type = 'application/json'
            r = self.get_history()
            return json.dumps(r)


compliancemgr = ComplianceManager()
