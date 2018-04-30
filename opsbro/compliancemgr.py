import time
import os
import json
import glob
import imp
from collections import deque
import traceback

from .log import LoggerFactory
from .stop import stopper
from .httpdaemon import http_export, response
from .evaluater import evaluater
from .util import make_dir
from .topic import topiker, TOPIC_SYSTEM_COMPLIANCE

# Global logger for this part
logger = LoggerFactory.create_logger('compliance')

COMPLIANCE_STATE_COLORS = {'COMPLIANT': 'green', 'FIXED': 'cyan', 'ERROR': 'red', 'UNKNOWN': 'grey', 'NOT-ELIGIBLE': 'grey'}
COMPLIANCE_LOG_COLORS = {'SUCCESS': 'green', 'ERROR': 'red', 'FIX': 'cyan', 'COMPLIANT': 'green'}
COMPLIANCE_STATES = ['COMPLIANT', 'FIXED', 'ERROR', 'UNKNOWN', 'NOT-ELIGIBLE']


class ComplianceRuleEnvironment(object):
    def __init__(self, env_def):
        self.name = env_def.get('name', 'no name')
        self.parameters = env_def.get('parameters', {})
        self.if_ = env_def.get('if', 'True')
        self.post_commands = env_def.get('post_commands', [])
    
    
    def get_name(self):
        return self.name
    
    
    def get_parameters(self):
        return self.parameters
    
    
    def get_if(self):
        return self.if_
    
    
    def get_post_commands(self):
        return self.post_commands


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


class Compliance(object):
    def __init__(self, pack_name, pack_level, name, mode, verify_if, rule_defs):
        self.pack_name = pack_name
        self.pack_level = pack_level
        self.name = name
        self.mode = mode
        self.verify_if = verify_if
        
        self.__state = 'UNKNOWN'
        self.__old_state = 'UNKNOWN'
        
        self.rules = []
        nb_rules = len(rule_defs)
        idx = 0
        for rule_def in rule_defs:
            idx += 1
            rule = Rule(pack_name, pack_level, mode, self.name, rule_def, idx, nb_rules)
            self.rules.append(rule)
    
    
    def get_name(self):
        return self.name
    
    
    def get_state(self):
        return self.__state
    
    
    def get_verify_if(self):
        return self.verify_if
    
    
    def set_not_eligible(self):
        for rule in self.rules:
            rule.set_not_eligible()
    
    
    def __set_state(self, state):
        if self.__state == state:
            return
        
        self.__old_state = self.__state
        self.__state = state
        logger.info('Compliance rule %s switch from %s to %s' % (self.name, self.__old_state, self.__state))
    
    
    def get_history_entries(self):
        history_entries = []
        for rule in self.rules:
            history_entry = rule.get_history_entry()
            if history_entry:
                history_entries.append(history_entry)
        return history_entries
    
    
    # Get the most important rule
    #       0          1       2       3           4
    # NOT-ELIGIBLE > ERROR > FIXED > COMPLIANT > UNKNOWN
    def compute_state(self):
        computed_state_ids = {'NOT-ELIGIBLE': 0, 'ERROR': 1, 'FIXED': 2, 'COMPLIANT': 3, 'UNKNOWN': 4}
        computed_state_reverse = {0: 'NOT-ELIGIBLE', 1: 'ERROR', 2: 'FIXED', 3: 'COMPLIANT', 4: 'UNKNOWN'}
        computed_state_id = 4
        for rule in self.rules:
            state = rule.get_state()
            if state == 'NOT-ELIGIBLE':
                self.__set_state(state)
                return
            state_id = computed_state_ids.get(state)
            if state_id < computed_state_id:
                computed_state_id = state_id
        # Get back the state
        computed_state = computed_state_reverse.get(computed_state_id)
        self.__set_state(computed_state)
        return
    
    
    def get_rules(self):
        return self.rules
    
    
    def reset(self):
        for rule in self.rules:
            rule.reset()
    
    
    # Dump our state, and our rules ones
    def get_json_dump(self):
        r = {'name': self.name, 'state': self.__state, 'old_state': self.__old_state, 'mode': self.mode, 'pack_level': self.pack_level, 'pack_name': self.pack_name, 'rules': []}
        
        for rule in self.rules:
            j = rule.get_json_dump()
            r['rules'].append(j)
        return r
    
    
    def add_error(self, error):
        for rule in self.rules:
            rule.add_error(error)
    
    
    def set_error(self):
        for rule in self.rules:
            rule.set_error()


class Rule(object):
    def __init__(self, pack_name, pack_level, mode, compliance_name, rule_def, idx, nb_rules):
        self.rule_def = rule_def
        self.compliance_name = compliance_name
        # If no name, we can take compliance name if it's the only rule
        # or the index if ther are more
        self.name = self.rule_def.get('name', None)
        if self.name is None:
            if nb_rules == 1:
                self.name = compliance_name
            else:
                self.name = 'step %d' % idx
        self.type = self.rule_def.get('type')
        self.environments = deque()
        env_defs = self.rule_def.get('environments', [])
        for env_def in env_defs:
            env = ComplianceRuleEnvironment(env_def)
            self.environments.append(env)
        self.post_commands = self.rule_def.get('post_commands', [])
        self.variable_defs = self.rule_def.get('variables', {})
        self.pack_name = pack_name
        self.pack_level = pack_level
        self.mode = mode
        
        self.__state = 'UNKNOWN'
        self.__old_state = 'UNKNOWN'
        self.__infos = []
        self.__did_change = False
        self.reset()
    
    
    def reset(self):
        self.__did_change = False
        self.__infos = []
    
    
    def get_mode(self):
        mode = self.mode
        if mode not in ['audit', 'enforcing']:
            err = 'RULE: %s mode %s is unknown. Should be audit or enforcing' % (self.get_name(), mode)
            self.add_error(err)
            self.set_error()
            return None
        return mode
    
    
    def get_type(self):
        return self.type
    
    
    def get_post_commands(self):
        return self.post_commands
    
    
    def get_name(self):
        return self.name
    
    
    def __get_variables(self):
        variables_params = self.variable_defs
        
        # We need to evaluate our variables if there are some
        variables = {}
        for (k, expr) in variables_params.iteritems():
            try:
                variables[k] = evaluater.eval_expr(expr)
            except Exception, exp:
                err = 'RULE: %s Variable %s (%s) evaluation did fail: %s' % (self.get_name(), k, expr, exp)
                self.add_error(err)
                self.set_error()
                return None
        return variables
    
    
    def get_first_matching_environnement(self):
        variables = self.__get_variables()
        if variables is None:
            return None
        
        for env in self.environments:
            if_ = env.get_if()
            env_name = env.get_name()
            try:
                do_match = evaluater.eval_expr(if_, variables=variables)
                if do_match:
                    logger.debug('Rule: %s We find a matching envrionnement: %s' % (self.name, env_name))
                    return env
            except Exception, exp:
                err = 'Environnement %s: "if" rule %s did fail to evaluate: %s' % (env_name, if_, exp)
                self.add_error(err)
                self.set_error()
                return None
        return None
    
    
    def launch_post_commands(self, matching_env):
        import subprocess
        post_commands = matching_env.get_post_commands()
        _from = 'Environnement %s' % matching_env.get_name()
        
        if not post_commands:
            post_commands = self.post_commands
            _from = 'Rule'
        logger.debug('%s have %d post commands' % (_from, len(post_commands)))
        for command in post_commands:
            logger.info('Launching post command: %s' % command)
            p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, preexec_fn=os.setsid)
            stdout, stderr = p.communicate()
            stdout += stderr
            if p.returncode != 0:
                err = 'Post command %s did generate an error: %s' % (command, stdout)
                self.add_error(err)
                self.set_error()
                return False
            logger.info('Launching post command: %s SUCCESS' % command)
        return True
    
    
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
        logger.info('Compliance rule %s switch from %s to %s' % (self.name, self.__old_state, self.__state))
    
    
    def set_error(self):
        self.__set_state('ERROR')
    
    
    def set_compliant(self):
        self.__set_state('COMPLIANT')
    
    
    def set_fixed(self):
        self.__set_state('FIXED')
    
    
    def set_not_eligible(self):
        self.__set_state('NOT-ELIGIBLE')
    
    
    def get_state(self):
        return self.__state
    
    
    def get_json_dump(self):
        return {'name': self.name, 'state': self.__state, 'old_state': self.__old_state, 'infos': self.__infos, 'mode': self.mode, 'pack_level': self.pack_level, 'pack_name': self.pack_name, 'type': self.type, 'compliance_name': self.compliance_name}
    
    
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
    
    
    def import_compliance(self, compliance_def, full_path, file_name, mod_time=0, pack_name='', pack_level=''):
        name = compliance_def.get('name', file_name)
        mode = compliance_def.get('mode', 'audit')
        if mode not in ('audit', 'enforcing'):
            logger.error('The compliance definition got a wrong mode :%s' % mode)
            return
        verify_if = compliance_def.get('verify_if', 'True')
        
        rule_def = compliance_def.get('rule', None)
        if rule_def is not None:
            rule_defs = [rule_def]
        else:
            # Looks if there are rules
            rule_defs = compliance_def.get('rules', None)
            if not rule_defs:
                logger.error('The compliance definition is missing a rule (and rules) entry :%s' % full_path)
                return
        for rule_def in rule_defs:
            rule_type = rule_def.get('type')
            if not rule_type:
                logger.error('The compliance definition is missing a rule type entry :%s' % full_path)
                return
        compliance = Compliance(pack_name, pack_level, name, mode, verify_if, rule_defs)
        
        # Add it into the list
        self.compliances[full_path] = compliance
    
    
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
        for (compliance_id, compliance) in self.compliances.iteritems():
            verify_if = compliance.get_verify_if()
            name = compliance.get_name()
            try:
                r = evaluater.eval_expr(verify_if)
                if not r:
                    compliance.set_not_eligible()
                    continue
            except Exception, exp:
                err = ' (%s) if rule (%s) evaluation did fail: %s' % (name, verify_if, exp)
                logger.error(err)
                compliance.add_error(err)
                compliance.set_error()
                continue
            
            # Reset previous errors
            compliance.reset()
            # Now launch rules
            for rule in compliance.get_rules():
                logger.debug('Execute compliance rule: %s' % rule)
                _type = rule.get_type()
                
                drv = self.drivers.get(_type)
                if drv is None:
                    logger.error('Cannot execute rule (%s) as the type is unknown: %s' % (name, _type))
                    continue
                try:
                    drv.launch(rule)
                except Exception:
                    err = 'The compliance driver %s did crash with the rule %s: %s' % (drv.name, name, str(traceback.format_exc()))
                    logger.error(err)
                    rule.add_error(err)
                    rule.set_error()
                    compliance.compute_state()
                    break
            compliance.compute_state()
            history_entries = compliance.get_history_entries()
            for history_entry in history_entries:
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
            if topiker.is_topic_enabled(TOPIC_SYSTEM_COMPLIANCE):
                self.launch_compliances()
            self.did_run = True
            # For each changes, we write a history entry
            self.__write_history_entry()
            time.sleep(1)
    
    
    def get_infos(self):
        counts = {}
        for state in COMPLIANCE_STATES:
            counts[state] = 0
        compliances = self.compliances.values()
        for c in compliances:
            counts[c.get_state()] += 1
        return counts
    
    
    def get_rule_state(self, rule_name):
        for compliance in self.compliances.values():
            if compliance.get_name() == rule_name:
                return compliance.get_state()
        return 'UNKNOWN'
    
    
    def export_http(self):
        @http_export('/compliance/state', method='GET')
        def get_compliance_state():
            response.content_type = 'application/json'
            nc = {}
            for (c_id, compliance) in self.compliances.iteritems():
                nc[c_id] = compliance.get_json_dump()
            return json.dumps(nc)
        
        
        @http_export('/compliance/history', method='GET')
        def get_compliance_history():
            response.content_type = 'application/json'
            r = self.get_history()
            return json.dumps(r)


compliancemgr = ComplianceManager()
