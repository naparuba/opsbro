from opsbro.evaluater import evaluater
from opsbro.systempacketmanager import get_systepacketmgr
from opsbro.compliancemgr import InterfaceComplianceDriver


class PackageInstallDriver(InterfaceComplianceDriver):
    name = 'package-install'
    
    
    def __init__(self):
        super(PackageInstallDriver, self).__init__()
    
    
    # environments:   <- take first to win
    #        - name: ubuntu  <- for display
    #         if:   "{{collector.system.os.linux.distribution}} == 'ubuntu'"   <- if rule to enable env or not
    #         packages:  <-- what to install if succeed
    #             - nginx
    #             - bash
    #         - OTHERS
    def launch(self, rule):
        parameters = rule.get_parameters()
        mode = rule.get_mode()
        
        did_error = False
        
        variables_params = parameters.get('variables', {})
        
        # We need to evaluate our variables if there are some
        variables = {}
        for (k, expr) in variables_params.iteritems():
            try:
                variables[k] = evaluater.eval_expr(expr)
            except Exception, exp:
                err = 'Variable %s (%s) evaluation did fail: %s' % (k, expr, exp)
                rule.add_error(err)
                rule.set_error()
                return
        
        # Find the environnement we match
        envs = parameters.get('environments', [])
        did_find_env = False
        env_name = ''
        env_packages = None
        for e in envs:
            if_ = e.get('if', None)
            env_name = e.get('name')
            env_packages = e.get('packages')
            
            try:
                do_match = evaluater.eval_expr(if_, variables=variables)
            except Exception, exp:
                err = 'Environnement %s: "if" rule %s did fail to evaluate: %s' % (env_name, if_, exp)
                rule.add_error(err)
                do_match = False
                did_error = True
            
            if do_match:
                self.logger.debug('Rule: %s We find a matching envrionnement: %s' % (self.name, env_name))
                did_find_env = True
                break
        
        if not did_find_env:
            # If we did match no environement
            err = 'No environnements did match, cannot solve packages installation'
            rule.add_error(err)
            rule.set_error()
            return
        
        # Now look if we are compliant, or not
        packages_to_install = []
        systepacketmgr = get_systepacketmgr()
        for package in env_packages:
            is_installed = systepacketmgr.has_package(package)
            self.logger.debug('(%s) is package %s installed? => %s' % (env_name, package, is_installed))
            if not is_installed:
                packages_to_install.append(package)
            else:
                txt = 'Environnement %s: the package %s is installed.' % (env_name, package)
                rule.add_compliance(txt)
        
        # If there is no packages to install, we are done in a good way
        if not packages_to_install:
            txt = 'All packages are already installed'
            rule.add_compliance(txt)
            rule.set_compliant()
            return
        
        # Ok we are not compliant, we need to fix (if allowed) some packages
        self.logger.debug('Installor:: (%s)  in the env %s, trying to detect which packages need to be installed (because they are not currently) => %s ' % (self.name, env_name, ','.join(packages_to_install)))
        for pkg in packages_to_install:
            err = 'Environnement %s: need to install package: %s' % (env_name, pkg)
            rule.add_error(err)
            if mode == 'enforcing':
                try:
                    systepacketmgr.install_package(pkg)
                    txt = 'Environnement %s: package %s is now installed' % (env_name, pkg)
                    rule.add_fix(txt)
                except Exception, exp:
                    err = 'Environnement %s: package (%s) installation fail: %s' % (env_name, pkg, exp)
                    rule.add_error(err)
                    did_error = True
            else:
                err = 'Environnement %s: the package %s is not installed' % (env_name, pkg)
                rule.add_error(err)
        
        # If we fail at least one package, exit it
        if did_error:
            rule.set_error()
            return
        
        # We did fix all package, cool
        txt = 'Environnement %s: all packages are now installed' % env_name
        rule.add_fix(txt)
        rule.set_fixed()
        return
