import time
import json

from kunai.log import LoggerFactory
from kunai.stop import stopper
from kunai.httpdaemon import http_export, response
from kunai.evaluater import evaluater
from kunai.systempacketmanager import systepacketmgr

# Global logger for this part
logger = LoggerFactory.create_logger('installor')


class Environment(object):
    def __init__(self, name, if_, packages):
        self.name = name
        self.if_ = if_
        self.packages = packages
    
    
    def do_match(self):
        logger.debug('   Environment:: (%s) do_match:: evaluating  %s ' % (self.name, self.if_))
        try:
            r = evaluater.eval_expr(self.if_)
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
    def __init__(self, o):
        self.name = o.get('name')
        self.note = o.get('note', '')
        self.if_ = o.get('if', None)
        self.environments = []
        
        envs = o.get('environments', [])
        for e in envs:
            if_ = e.get('if', None)
            name = e.get('name')
            packages = e.get('packages')
            env = Environment(name, if_, packages)
            self.environments.append(env)
    
    
    def execute(self):
        logger.debug('Installor:: (%s)  evaluating :: %s' % (self.name, self.if_))
        try:
            r = evaluater.eval_expr(self.if_)
        except Exception, exp:
            logger.error('[%s] Execution of the if rule did fail: (%s)=>%s' % (self.name, self.if_, exp))
            return
        logger.debug('Installor:: (%s)  execute:: %s => %s' % (self.name, self.if_, r))
        for env in self.environments:
            do_match = env.do_match()
            if do_match:
                logger.debug('Installor:: (%s)  we find a matching envrionnement: %s' % (self.name, env.name))
                # Maybe
                packages_to_install = env.which_packages_are_need_to_be_installed()
                logger.debug('Installor:: (%s)  in the env %s, which packages need to be installed (because they are not currently) => %s ' % (self.name, env.name, ','.join(packages_to_install)))
                break


class InstallorMgr(object):
    def __init__(self):
        self.install_rules = []
    
    
    def import_installor(self, o, fname, gname, mod_time=0):
        installor = Installor(o)
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
