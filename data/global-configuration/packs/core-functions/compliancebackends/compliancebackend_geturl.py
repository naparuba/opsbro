import urllib2
import shutil
import os
import urlparse
import ssl
import hashlib

from opsbro.evaluater import evaluater
from opsbro.compliancemgr import InterfaceComplianceDriver
from opsbro.util import make_dir


class GetURLDriver(InterfaceComplianceDriver):
    name = 'get-url'
    
    
    def __init__(self):
        super(GetURLDriver, self).__init__()
        self.ssl_context = ssl._create_unverified_context()
    
    
    # environments:   <- take first to win
    #        - name: ubuntu  <- for display
    #         if:   "{{collector.system.os.linux.distribution}} == 'ubuntu'"   <- if rule to enable env or not
    #         url:  <-- what to download
    #         dest_path: <-- what to download
    #         sha1: <-- check if the sha1 is valid
    #         md5:  <-- check if the md5 is valid
    #             - bash
    #         - OTHERS
    def launch(self, rule):
        import subprocess
        
        parameters = rule.get_parameters()
        mode = rule.get_mode()
        
        if mode not in ['audit', 'enforcing']:
            err = 'Mode %s is unknown' % mode
            rule.add_error(err)
            rule.set_error()
            return
        
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
        url = ''
        dest_directory = ''
        sha1 = ''
        md5 = ''
        post_commands = []
        for e in envs:
            if_ = e.get('if', None)
            env_name = e.get('name')
            dest_directory = e.get('dest_directory')
            url = e.get('url')
            sha1 = e.get('sha1', '')
            md5 = e.get('md5', '')
            post_commands = e.get('post_commands', [])
            
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
            err = 'No environnements did match, cannot solve uri download'
            rule.add_error(err)
            rule.set_error()
            return
        
        if not url:
            err = 'No url defined, cannot solve uri download'
            rule.add_error(err)
            rule.set_error()
            return
        
        if not dest_directory:
            err = 'No dest_directory defined, cannot solve uri download'
            rule.add_error(err)
            rule.set_error()
            return
        
        parsed_uri = urlparse.urlparse(url)
        file_name = os.path.basename(parsed_uri.path)
        self.logger.debug("TRY DOWNLOADING %s => %s " % (url, file_name))
        
        # If we want to download in a directory
        if not os.path.exists(dest_directory):
            make_dir(dest_directory)
        self.logger.debug("MKDIR OK")
        
        dest_file = os.path.join(dest_directory, file_name)
        tmp_file = dest_file + '.tmp'
        
        # If the file already exists, there is no packages to install, we are done in a good way
        if os.path.exists(dest_file):
            txt = 'The file at %s is already present at %s' % (url, dest_file)
            rule.add_compliance(txt)
            rule.set_compliant()
            return
        
        # If audit mode: we should exit now
        if mode == 'audit':
            err = 'The file %s is not present at %s' % (url, dest_file)
            rule.add_error(err)
            rule.set_error()
            return
        
        self.logger.debug('START DOWNLOAd', url)
        try:
            filedata = urllib2.urlopen(url, context=self.ssl_context)
            data = filedata.read()
        except Exception, exp:
            err = 'ERROR: downloading the uri: %s did fail withthe error: %s' % (url, exp)
            print err
            rule.add_error(err)
            rule.set_error()
            return
            self.logger.debug("DOWNLOADED", len(data))
        
        if sha1:
            sha1_hash = hashlib.sha1(data).hexdigest()
            if sha1 != sha1_hash:
                err = 'ERROR: the file %s sha1 hash %s did not match defined one: %s' % (url, sha1_hash, sha1)
                print err
                rule.add_error(err)
                rule.set_error()
                return
        
        if md5:
            md5_hash = hashlib.md5(data).hexdigest()
            if md5 != md5_hash:
                err = 'ERROR: the file %s md5 hash %s did not match defined one: %s' % (url, md5_hash, md5)
                print err
                rule.add_error(err)
                rule.set_error()
                return
        
        self.logger.debug("WRITING FILE")
        try:
            with open(tmp_file, 'wb') as f:
                f.write(data)
        except Exception, exp:
            err = 'ERROR: cannot save the file %s: %s' % (tmp_file, exp)
            print err
            rule.add_error(err)
            rule.set_error()
            return
        
        self.logger.debug("MOVING FILE")
        try:
            shutil.move(tmp_file, dest_file)
        except Exception, exp:
            err = 'ERROR: cannot save the file %s: %s' % (dest_file, exp)
            print err
            rule.add_error(err)
            rule.set_error()
            return
        self.logger.debug("SAVED TO", dest_file)
        
        for command in post_commands:
            self.logger.info('Launching post command: %s' % command)
            p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)  # , preexec_fn=os.setsid)
            stdout, stderr = p.communicate()
            stdout += stderr
            if p.returncode != 0:
                err = 'Post command %s did generate an error: %s' % (command, stdout)
                rule.add_error(err)
                rule.set_error()
                return
            self.logger.info('Launching post command: %s SUCCESS' % command)
        
        if did_error:
            rule.set_error()
            return
        
        # We did do the job
        txt = 'The file at %s was download at %s' % (url, dest_file)
        rule.add_fix(txt)
        rule.set_fixed()
        return
