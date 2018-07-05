import time
import os
import json
import glob
import imp
from collections import deque
import traceback

from .log import LoggerFactory
from .stop import stopper
from .httpdaemon import http_export, response, request
from .evaluater import evaluater
from .topic import topiker, TOPIC_SYSTEM_COMPLIANCE
from .handlermgr import handlermgr
from .basemanager import BaseManager
from .misc.six import add_metaclass
from .util import bytes_to_unicode, exec_command

# Global logger for this part
logger = LoggerFactory.create_logger('compliance')


class COMPLIANCE_STATES(object):
    RUNNING = 'RUNNING'
    COMPLIANT = 'COMPLIANT'
    FIXED = 'FIXED'
    ERROR = 'ERROR'
    UNKNOWN = 'UNKNOWN'  # cannot launch it
    PENDING = 'PENDING'  # never launched
    NOT_ELIGIBLE = 'NOT-ELIGIBLE'


COMPLIANCE_STATE_COLORS = {COMPLIANCE_STATES.RUNNING     : 'magenta',
                           COMPLIANCE_STATES.COMPLIANT   : 'green',
                           COMPLIANCE_STATES.FIXED       : 'cyan',
                           COMPLIANCE_STATES.ERROR       : 'red',
                           COMPLIANCE_STATES.PENDING     : 'grey',
                           COMPLIANCE_STATES.NOT_ELIGIBLE: 'grey'}
ALL_COMPLIANCE_STATES = COMPLIANCE_STATE_COLORS.keys()
COMPLIANCE_LOG_COLORS = {'SUCCESS': 'green', 'ERROR': 'red', 'FIX': 'cyan', 'COMPLIANT': 'green'}


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


class ComplianceMetaClass(type):
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


@add_metaclass(ComplianceMetaClass)
# Base class for hosting driver. MUST be used
class InterfaceComplianceDriver(object):
    name = '__MISSING__NAME__'
    
    
    @classmethod
    def get_sub_class(cls):
        return cls.__inheritors__
    
    
    def __init__(self):
        self.logger = logger
    
    
    def launch(self, rule):
        rule.add_error('The driver %s is missing launch action.' % self.__class__)


class Rule(object):
    def __init__(self, pack_name, pack_level, mode, compliance_name, rule_def, idx, nb_rules):
        self.compliance_name = compliance_name
        # If no name, we can take compliance name if it's the only rule
        # or the index if ther are more
        self.name = rule_def.get('name', None)
        if self.name is None:
            if nb_rules == 1:
                self.name = compliance_name
            else:
                self.name = 'step %d' % idx
        self.type = rule_def.get('type')
        self.environments = deque()
        env_defs = rule_def.get('environments', [])
        
        # If there are no environnements, fake one with the parameters
        if len(env_defs) == 0:
            # Just name and parameters, no if or post commands are they will be global
            fake_env_def = {'name': self.name, 'parameters': rule_def.get('parameters', {})}
            env_defs = [fake_env_def]
        
        for env_def in env_defs:
            env = ComplianceRuleEnvironment(env_def)
            self.environments.append(env)
        
        self.post_commands = rule_def.get('post_commands', [])
        self.variable_defs = rule_def.get('variables', {})
        self.pack_name = pack_name
        self.pack_level = pack_level
        self.mode = mode
        
        self.__state = COMPLIANCE_STATES.PENDING
        self.__old_state = COMPLIANCE_STATES.PENDING
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
        for (k, expr) in variables_params.items():
            try:
                variables[k] = evaluater.eval_expr(expr)
            except Exception as exp:
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
            except Exception as exp:
                err = 'Environnement %s: "if" rule %s did fail to evaluate: %s' % (env_name, if_, exp)
                self.add_error(err)
                self.set_error()
                return None
        return None
    
    
    def launch_post_commands(self, matching_env):
        post_commands = matching_env.get_post_commands()
        _from = 'Environnement %s' % matching_env.get_name()
        
        if not post_commands:
            post_commands = self.post_commands
            _from = 'Rule'
        logger.debug('%s have %d post commands' % (_from, len(post_commands)))
        for command in post_commands:
            logger.info('Launching post command: %s' % command)
            try:
                return_code, stdout, stderr = exec_command(command)
                stdout += stderr
                if return_code != 0:
                    err = 'Post command %s did generate an error: %s' % (command, stdout)
                    self.add_error(err)
                    self.set_error()
                    return False
                logger.info('Launching post command: %s SUCCESS' % command)
            except Exception as exp:
                err = 'Post command %s did generate an error: %s' % (command, exp)
                self.add_error(err)
                self.set_error()
                return False
        return True
    
    
    def add_success(self, txt):
        self.__infos.append({'state': 'SUCCESS', 'text': txt})
    
    
    def add_error(self, txt):
        self.__infos.append({'state': 'ERROR', 'text': txt})
    
    
    def add_fix(self, txt):
        self.__infos.append({'state': 'FIX', 'text': txt})
    
    
    def add_compliance(self, txt):
        self.__infos.append({'state': 'COMPLIANT', 'text': txt})
    
    
    def is_in_error(self):
        return self.__state == COMPLIANCE_STATES.ERROR
    
    
    def __set_state(self, state):
        if self.__state == state:
            return
        
        self.__did_change = True
        self.__old_state = self.__state
        self.__state = state
        logger.info('Compliance rule %s switch from %s to %s' % (self.name, self.__old_state, self.__state))
    
    
    def set_error(self):
        self.__set_state(COMPLIANCE_STATES.ERROR)
    
    
    def set_compliant(self):
        self.__set_state(COMPLIANCE_STATES.COMPLIANT)
    
    
    def set_fixed(self):
        self.__set_state(COMPLIANCE_STATES.FIXED)
    
    
    def set_unknown(self):
        self.__set_state(COMPLIANCE_STATES.UNKNOWN)
    
    
    def set_not_eligible(self):
        self.__set_state(COMPLIANCE_STATES.NOT_ELIGIBLE)
    
    
    def get_state(self):
        return self.__state
    
    
    def get_json_dump(self):
        return {'name': self.name, 'state': self.__state, 'old_state': self.__old_state, 'infos': self.__infos, 'mode': self.mode, 'pack_level': self.pack_level, 'pack_name': self.pack_name, 'type': self.type, 'compliance_name': self.compliance_name}
    
    
    def get_history_entry(self):
        if not self.__did_change:
            return None
        return self.get_json_dump()


class Compliance(object):
    # fo notification, not all state changes are interesting
    # PENDING -> NOT-ELIGIBLE is not an interesting email to receive, so only list here state
    # changes with a real meaning, like COMPLIANT->ERROR for example
    notification_interesting_state_changes = set([
        # FROM, TO
        
        # Pending ->
        (COMPLIANCE_STATES.PENDING, COMPLIANCE_STATES.FIXED),
        (COMPLIANCE_STATES.PENDING, COMPLIANCE_STATES.ERROR),
        
        # Unknown ->
        (COMPLIANCE_STATES.UNKNOWN, COMPLIANCE_STATES.FIXED),
        (COMPLIANCE_STATES.UNKNOWN, COMPLIANCE_STATES.ERROR),
        
        # NOT-ELIGIBLE ->
        (COMPLIANCE_STATES.NOT_ELIGIBLE, COMPLIANCE_STATES.FIXED),
        (COMPLIANCE_STATES.NOT_ELIGIBLE, COMPLIANCE_STATES.ERROR),
        
        # FIXED ->
        # FIXEd-> compliant is a normal step, we do nto notify about it
        (COMPLIANCE_STATES.FIXED, COMPLIANCE_STATES.ERROR),  # did just break
        
        # Compliant ->
        (COMPLIANCE_STATES.COMPLIANT, COMPLIANCE_STATES.ERROR),
        
        # ERROR->
        (COMPLIANCE_STATES.ERROR, COMPLIANCE_STATES.FIXED),  # the agent did fixed it
        (COMPLIANCE_STATES.ERROR, COMPLIANCE_STATES.COMPLIANT),  # the admin did fixed it
    
    ])
    
    # When computing our state based on rules one:
    # Get the most important rule state
    #       0          1       2       3           4          5
    # NOT-ELIGIBLE > ERROR > FIXED > COMPLIANT > UNKNOWN > PENDING
    computed_state_ids = {COMPLIANCE_STATES.NOT_ELIGIBLE: 0,
                          COMPLIANCE_STATES.ERROR       : 1,
                          COMPLIANCE_STATES.FIXED       : 2,
                          COMPLIANCE_STATES.COMPLIANT   : 3,
                          COMPLIANCE_STATES.UNKNOWN     : 4,
                          COMPLIANCE_STATES.PENDING     : 5,
                          }
    computed_state_reverse = {0: COMPLIANCE_STATES.NOT_ELIGIBLE,
                              1: COMPLIANCE_STATES.ERROR,
                              2: COMPLIANCE_STATES.FIXED,
                              3: COMPLIANCE_STATES.COMPLIANT,
                              4: COMPLIANCE_STATES.UNKNOWN,
                              5: COMPLIANCE_STATES.PENDING,
                              }
    least_significative_computed_state_ids = 5
    
    
    def __init__(self, pack_name, pack_level, name, mode, verify_if, rule_defs):
        self.pack_name = pack_name
        self.pack_level = pack_level
        self.name = name
        self.mode = mode
        self.verify_if = verify_if
        
        self.__forced = False
        
        self.__state = COMPLIANCE_STATES.PENDING
        self.__old_state = COMPLIANCE_STATES.PENDING
        
        self.__current_step = ''
        self.__is_running = False
        
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
    
    
    def get_old_state(self):
        return self.__old_state
    
    
    def get_verify_if(self):
        return self.verify_if
    
    
    def set_not_eligible(self):
        for rule in self.rules:
            rule.set_not_eligible()
    
    
    def set_forced(self):
        self.__forced = True
    
    
    # Look at the old state -> state change, and look if it's in the list of
    # interesting changes
    def is_last_change_interesting_for_notification(self):
        return (self.__old_state, self.__state) in self.notification_interesting_state_changes
    
    
    def should_be_launched(self):
        if self.__forced:
            return True
        
        verify_if = self.get_verify_if()
        try:
            r = evaluater.eval_expr(verify_if)
            if not r:
                self.set_not_eligible()
                return False
            return True
        except Exception as exp:
            err = ' (%s) if rule (%s) evaluation did fail: %s' % (self.name, verify_if, exp)
            logger.error(err)
            self.add_error(err)
            self.set_error()
            return False
    
    
    def __set_state(self, state):
        if self.__state == state:
            return False
        
        self.__old_state = self.__state
        self.__state = state
        logger.info('Compliance rule %s switch from %s to %s' % (self.name, self.__old_state, self.__state))
        return True
    
    
    def get_history_entries(self):
        history_entries = []
        for rule in self.rules:
            history_entry = rule.get_history_entry()
            if history_entry:
                history_entries.append(history_entry)
        return history_entries
    
    
    # Get the most important rule
    #       0          1       2       3           4          5
    # NOT-ELIGIBLE > ERROR > FIXED > COMPLIANT > UNKNOWN > PENDING
    def compute_state(self):
        computed_state_id = self.least_significative_computed_state_ids
        for rule in self.rules:
            state = rule.get_state()
            if state == COMPLIANCE_STATES.NOT_ELIGIBLE:
                did_change = self.__set_state(state)
                return did_change
            state_id = self.computed_state_ids.get(state)
            if state_id < computed_state_id:
                computed_state_id = state_id
        # Get back the state
        computed_state = self.computed_state_reverse.get(computed_state_id)
        did_change = self.__set_state(computed_state)
        # And so we did finish
        self.__is_running = False
        self.__current_step = ''
        return did_change
    
    
    def get_rules(self):
        return self.rules
    
    
    # Before run, reset all our rules to drop old infos/state
    # and set us as running
    def prepare_running(self):
        for rule in self.rules:
            rule.reset()
        self.__is_running = True
    
    
    # Dump our state, and our rules ones
    def get_json_dump(self):
        r = {'name'      : self.name, 'state': self.__state, 'old_state': self.__old_state,
             'mode'      : self.mode,
             'pack_level': self.pack_level, 'pack_name': self.pack_name,
             'is_running': self.__is_running, 'current_step': self.__current_step,
             'rules'     : []}
        
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
    
    
    def set_unknown(self):
        for rule in self.rules:
            rule.set_unknown()
    
    
    def set_current_step(self, rule):
        self.__current_step = rule.get_name()


class ComplianceManager(BaseManager):
    history_directory_suffix = 'compliance'
    
    
    def __init__(self):
        super(ComplianceManager, self).__init__()
        self.compliances = {}
        self.did_run = False
        self.drivers = {}
        
        self.logger = logger
    
    
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
        
        # The configuration backend is ready, we can assert the presence of our history directory
        self.prepare_history_directory()
    
    
    @staticmethod
    def load_directory(directory, pack_name='', pack_level=''):
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
            except Exception as exp:
                logger.error('Cannot load compliance driver %s: %s' % (fname, exp))
    
    
    def import_compliance(self, compliance_def, full_path, file_name, mod_time=0, pack_name='', pack_level=''):
        name = compliance_def.get('name', file_name)
        mode = compliance_def.get('mode', 'audit')
        if mode not in ('audit', 'enforcing'):
            logger.error('The compliance definition got a wrong mode :%s' % mode)
            return
        verify_if = compliance_def.get('verify_if', 'False')
        
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
    
    
    def __launch_compliances(self):
        for (compliance_id, compliance) in self.compliances.items():
            
            name = compliance.get_name()
            
            should_be_launched = compliance.should_be_launched()
            if not should_be_launched:
                continue
            
            # Reset previous errors
            compliance.prepare_running()
            one_step_in_error = False
            
            # Now launch rules
            # TODO: get all of this in the Compliance class
            for rule in compliance.get_rules():
                # Let the compliance know which rule is launched
                compliance.set_current_step(rule)
                logger.debug('Execute compliance rule: %s' % rule)
                _type = rule.get_type()
                
                if one_step_in_error:
                    rule.set_unknown()
                    continue
                
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
                
                if rule.is_in_error():
                    one_step_in_error = True
            
            did_change = compliance.compute_state()
            history_entries = compliance.get_history_entries()
            for history_entry in history_entries:
                self.add_history_entry(history_entry)
            
            # We should give the compliance launch to handlers module, but only when the
            # compliance state do change and the change is an interesting one
            if did_change and compliance.is_last_change_interesting_for_notification():
                handlermgr.launch_compliance_handlers(compliance, did_change=did_change)
    
    
    def do_compliance_thread(self):
        from .collectormanager import collectormgr
        # if the collector manager did not run, our evaluation can be invalid, so wait for all collectors to run at least once
        while collectormgr.did_run == False:
            time.sleep(0.25)
        while not stopper.interrupted:
            if topiker.is_topic_enabled(TOPIC_SYSTEM_COMPLIANCE):
                self.__launch_compliances()
            self.did_run = True
            # For each changes, we write a history entry
            self.write_history_entry()
            time.sleep(1)
    
    
    def get_infos(self):
        counts = {}
        for state in ALL_COMPLIANCE_STATES:
            counts[state] = 0
        compliances = self.compliances.values()
        for c in compliances:
            counts[c.get_state()] += 1
        return counts
    
    
    def set_compliance_to_forced(self, compliance_name):
        compliance = self.__get_rule_by_name(compliance_name)
        if compliance is None:
            return False
        compliance.set_forced()
        return True
    
    
    def __get_rule_by_name(self, rule_name):
        for compliance in self.compliances.values():
            if compliance.get_name() == rule_name:
                return compliance
        return None
    
    
    def get_rule_state(self, rule_name):
        compliance = self.__get_rule_by_name(rule_name)
        if compliance is not None:
            return compliance.get_state()
        return COMPLIANCE_STATES.UNKNOWN
    
    
    def export_http(self):
        @http_export('/compliance/state', method='GET')
        def get_compliance_state():
            response.content_type = 'application/json'
            nc = {}
            for (c_id, compliance) in self.compliances.items():
                nc[c_id] = compliance.get_json_dump()
            return json.dumps(nc)
        
        
        @http_export('/compliance/history', method='GET')
        def get_compliance_history():
            response.content_type = 'application/json'
            r = self.get_history()
            return json.dumps(r)
        
        
        @http_export('/compliance/launch', method='PUT', protected=True)
        def post_zone():
            response.content_type = 'application/json'
            
            compliance_name = request.body.getvalue()
            compliance_name = bytes_to_unicode(compliance_name)
            logger.info("HTTP: /compliance/launch launching compliance rule %s" % compliance_name)
            r = self.set_compliance_to_forced(compliance_name)
            return json.dumps(r)


compliancemgr = ComplianceManager()
