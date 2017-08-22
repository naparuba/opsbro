import time
import json

from opsbro.log import LoggerFactory
from opsbro.stop import stopper
from opsbro.httpdaemon import http_export, response
from opsbro.evaluater import evaluater
from opsbro.systempacketmanager import systepacketmgr

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
        
        envs = o.get('environments', [])
        for e in envs:
            if_ = e.get('if', None)
            name = e.get('name')
            packages = e.get('packages')
            env = Environment(name, if_, packages)
            self.environments.append(env)
    
    
    def get_variables_evals(self):
        res = {}
        for (k, expr) in self.variables.iteritems():
            try:
                res[k] = evaluater.eval_expr(expr)
            except Exception, exp:
                logger.error('Installor:: (%s)  Variable %s (%s) evaluation did fail: %s' % (self.name, k, expr, exp))
                return None
        return res
    
    
    def execute(self):
        logger.debug('Installor:: (%s)  evaluating :: %s' % (self.name, self.if_))
        try:
            r = evaluater.eval_expr(self.if_)
        except Exception, exp:
            logger.error('[%s] Execution of the if rule did fail: (%s)=>%s' % (self.name, self.if_, exp))
            return
        logger.debug('Installor:: (%s)  execute:: %s => %s' % (self.name, self.if_, r))
        if not r:
            logger.debug('Installor:: (%s) if rule do not match. Skip installer.' % (self.name))
            return
        # We need to evaluate our variables if there are some
        variables = self.get_variables_evals()
        if variables is None:
            logger.error('Installor:: (%s) some variables did fail, cannot continue the evaluation' % self.name)
            return
        
        for env in self.environments:
            do_match = env.do_match(variables)
            if do_match:
                logger.debug('Installor:: (%s)  we find a matching envrionnement: %s' % (self.name, env.name))
                # Maybe
                packages_to_install = env.which_packages_are_need_to_be_installed()
                logger.debug('Installor:: (%s)  in the env %s, which packages need to be installed (because they are not currently) => %s ' % (self.name, env.name, ','.join(packages_to_install)))
                for pkg in packages_to_install:
                    logger.debug('Installor:: (%s)  in the env %s : installing package: %s' % (self.name, env.name, pkg))
                    try:
                        systepacketmgr.install_package(pkg)
                    except Exception, exp:
                        logger.error('Installor:: (%s)  in the env %s : package (%s) installation fail: %s' % (self.name, env.name, pkg, exp))
                # always stop at the first env that match
                break


class InstallorMgr(object):
    def __init__(self):
        self.install_rules = []
    
    
    def import_installor(self, o, fname, gname, mod_time=0, pack_name='', pack_level=''):
        installor = Installor(o, pack_name=pack_name, pack_level=pack_level)
        self.install_rules.append(installor)
    
    
    def do_installer_thread(self):
        while not stopper.interrupted:
            logger.debug('Looking at installer need')
            for o in self.install_rules:
                logger.debug('Look at installing %s' % o.name)
                o.execute()
            time.sleep(1)
    
    
    def export_http(self):
        @http_export('/installers/')
        @http_export('/installers')
        def get_installers():
            response.content_type = 'application/json'
            return json.dumps(self.install_rules)


installormgr = InstallorMgr()
