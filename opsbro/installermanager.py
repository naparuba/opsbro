import time
import json
import os
import glob

from opsbro.log import LoggerFactory
from opsbro.stop import stopper
from opsbro.httpdaemon import http_export, response
from opsbro.evaluater import evaluater
from opsbro.systempacketmanager import get_systepacketmgr

# Global logger for this part
logger = LoggerFactory.create_logger('installor')


class Environment(object):
    def __init__(self, name, if_, packages):
        self.name = name
        self.if_ = if_
        self.packages = packages
    
    
    def do_match(self, variables):
        logger.debug('   Environment:: (%s) do_match:: evaluating  %s ' % (self.name, self.if_))
        try:
            r = evaluater.eval_expr(self.if_, variables=variables)
        except Exception, exp:
            logger.error('   Environnement:: (%s) if rule (%s) evaluation did fail: %s' % (self.name, self.if_, exp))
            return False
        logger.debug('   Environment:: (%s) do_match:: %s => %s' % (self.name, self.if_, r))
        return r
    
    
    def which_packages_are_need_to_be_installed(self):
        res = []
        systepacketmgr = get_systepacketmgr()
        for package in self.packages:
            is_installed = systepacketmgr.has_package(package)
            logger.debug('   Environnement:: (%s) is package %s already installed? => %s' % (self.name, package, is_installed))
            if not is_installed:
                res.append(package)
        return res


class Installor(object):
    def __init__(self, o, pack_name='', pack_level=''):
        self.name = o.get('name')
        self.pack_name = pack_name
        self.pack_level = pack_level
        self.note = o.get('note', '')
        self.if_ = o.get('if', None)
        self.environments = []
        self.variables = o.get('variables', {})
        
        self.__old_state = 'PENDING'
        self.__state = 'PENDING'
        self.__did_change = False
        self.__infos = []
        
        envs = o.get('environments', [])
        for e in envs:
            if_ = e.get('if', None)
            name = e.get('name')
            packages = e.get('packages')
            env = Environment(name, if_, packages)
            self.environments.append(env)
    
    
    def __set_state(self, state):
        if self.__state == state:
            return
        self.__old_state = self.__state
        self.__state = state
        self.__did_change = True
    
    
    def __set_state_error(self, txt):
        self.__infos.append({'state': 'ERROR', 'text': txt})
        self.__set_state('ERROR')
    
    
    def __set_state_not_need(self, txt):
        self.__infos.append({'state': 'INFO', 'text': txt})
        self.__set_state('NOT-NEED')
    
    
    def __set_state_ok(self, txt):
        self.__infos.append({'state': 'OK', 'text': txt})
        self.__set_state('OK')
    
    
    def __get_variables_evals(self):
        res = {}
        for (k, expr) in self.variables.iteritems():
            try:
                res[k] = evaluater.eval_expr(expr)
            except Exception, exp:
                logger.error('Installor:: (%s)  Variable %s (%s) evaluation did fail: %s' % (self.name, k, expr, exp))
                return None
        return res
    
    
    def execute(self):
        self.__did_change = False
        self.__infos = []
        logger.debug('Installor:: (%s)  evaluating :: %s' % (self.name, self.if_))
        try:
            r = evaluater.eval_expr(self.if_)
        except Exception, exp:
            err = '[%s] Execution of the if rule did fail: (%s)=>%s' % (self.name, self.if_, exp)
            self.__set_state_error(err)
            logger.error(err)
            return
        logger.debug('Installor:: (%s)  execute:: %s => %s' % (self.name, self.if_, r))
        if not r:
            txt = 'Installor:: (%s) if rule do not match. Skip installer.' % (self.name)
            logger.debug(txt)
            self.__set_state_not_need(txt)
            return
        # We need to evaluate our variables if there are some
        variables = self.__get_variables_evals()
        if variables is None:
            err = 'Installor:: (%s) some variables did fail, cannot continue the evaluation' % self.name
            self.__set_state_error(err)
            logger.error(err)
            return
        
        systepacketmgr = get_systepacketmgr()
        for env in self.environments:
            do_match = env.do_match(variables)
            if not do_match:
                continue
            logger.debug('Installor:: (%s)  we find a matching envrionnement: %s' % (self.name, env.name))
            
            # Maybe we are already OK, so we are already done
            if self.__state == 'OK':
                txt = 'Installor:: (%s) all packages are already installed.' % self.name
                self.__set_state_ok(txt)
                return
            
            packages_to_install = env.which_packages_are_need_to_be_installed()
            # If there is no packages to install, we are done in a good way
            if not packages_to_install:
                txt = 'Installor:: (%s) all packages are already installed.' % self.name
                self.__set_state_ok(txt)
                return
            
            logger.debug('Installor:: (%s)  in the env %s, trying to detect which packages need to be installed (because they are not currently) => %s ' % (self.name, env.name, ','.join(packages_to_install)))
            for pkg in packages_to_install:
                logger.info('Installor:: (%s)  in the env %s : installing package: %s' % (self.name, env.name, pkg))
                try:
                    systepacketmgr.install_package(pkg)
                    self.__did_change = True
                    self.__infos.append('Installor:: (%s)  in the env %s : installing package: %s' % (self.name, env.name, pkg))
                except Exception, exp:
                    err = 'Installor:: (%s)  in the env %s : package (%s) installation fail: %s' % (self.name, env.name, pkg, exp)
                    self.__set_state_error(err)
                    logger.error(err)
                    return
            
            txt = 'Installor:: (%s) packages installation OK' % self.name
            self.__set_state_ok(txt)
            return
        
        # If we did match no environement
        err = 'Installor:: (%s) no environnements did match, cannot sole packages installation' % self.name
        self.__set_state_error(err)
        return
    
    
    def get_json_dump(self):
        return {'name': self.name, 'infos': self.__infos, 'pack_level': self.pack_level, 'pack_name': self.pack_name}
    
    
    def get_history_entry(self):
        if not self.__did_change:
            return None
        return self.get_json_dump()


class InstallorMgr(object):
    def __init__(self):
        self.install_rules = []
        self.did_run = False
        
        self.history_directory = None
        self.__current_history_entry = []
    
    
    def import_installor(self, o, fname, gname, mod_time=0, pack_name='', pack_level=''):
        installor = Installor(o, pack_name=pack_name, pack_level=pack_level)
        self.install_rules.append(installor)
    
    
    def prepare_history_directory(self):
        # Prepare the history
        from .configurationmanager import configmgr
        data_dir = configmgr.get_data_dir()
        self.history_directory = os.path.join(data_dir, 'installer_history')
        logger.debug('Asserting existence of the installer history directory: %s' % self.history_directory)
        if not os.path.exists(self.history_directory):
            os.mkdir(self.history_directory)
    
    
    def do_installer_thread(self):
        while not stopper.interrupted:
            logger.debug('Looking at installer need')
            for o in self.install_rules:
                logger.debug('Look at installing %s' % o.name)
                o.execute()
                history_entry = o.get_history_entry()
                if history_entry:
                    self.add_history_entry(history_entry)
            self.did_run = True
            # For each changes, we write a history entry
            self.__write_history_entry()
            time.sleep(1)
    
    
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
    
    
    def get_state(self):
        return [o.get_json_dump() for o in self.install_rules]
    
    
    def export_http(self):
        @http_export('/installers/', method='GET')
        @http_export('/installers', method='GET')
        def get_installers():
            response.content_type = 'application/json'
            return json.dumps(self.install_rules)
        
        
        @http_export('/installers/state', method='GET')
        def get_installers_state():
            response.content_type = 'application/json'
            r = self.get_state()
            return json.dumps(r)
        
        
        @http_export('/installers/history', method='GET')
        def get_installers_history():
            response.content_type = 'application/json'
            r = self.get_history()
            return json.dumps(r)


installormgr = InstallorMgr()
