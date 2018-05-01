from __future__ import print_function
import urllib2
import shutil
import os
import urlparse
import ssl
import hashlib

from opsbro.compliancemgr import InterfaceComplianceDriver
from opsbro.util import make_dir


class GetURLDriver(InterfaceComplianceDriver):
    name = 'get-url'
    
    
    def __init__(self):
        super(GetURLDriver, self).__init__()
        
        # NOTE: ssl.SSLContext is only availabe on last python 2.7 versions
        if hasattr(ssl, 'SSLContext'):
            self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE
        else:
            self.ssl_context = None
    
    
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
        
        mode = rule.get_mode()
        if mode is None:
            return
        
        matching_env = rule.get_first_matching_environnement()
        if matching_env is None:
            return
        
        # Now we can get our parameters
        parameters = matching_env.get_parameters()
        dest_directory = parameters.get('dest_directory')
        url = parameters.get('url')
        sha1 = parameters.get('sha1', '')
        md5 = parameters.get('md5', '')
        
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
            args = {}
            if self.ssl_context:
                args['context'] = self.ssl_context
            filedata = urllib2.urlopen(url, **args)
            data = filedata.read()
        except Exception as exp:
            err = 'ERROR: downloading the uri: %s did fail withthe error: %s' % (url, exp)
            rule.add_error(err)
            rule.set_error()
            return
        self.logger.debug("DOWNLOADED", len(data))
        
        if sha1:
            sha1_hash = hashlib.sha1(data).hexdigest()
            if sha1 != sha1_hash:
                err = 'ERROR: the file %s sha1 hash %s did not match defined one: %s' % (url, sha1_hash, sha1)
                rule.add_error(err)
                rule.set_error()
                return
        
        if md5:
            md5_hash = hashlib.md5(data).hexdigest()
            if md5 != md5_hash:
                err = 'ERROR: the file %s md5 hash %s did not match defined one: %s' % (url, md5_hash, md5)
                rule.add_error(err)
                rule.set_error()
                return
        
        self.logger.debug("WRITING FILE")
        try:
            with open(tmp_file, 'wb') as f:
                f.write(data)
        except Exception as exp:
            err = 'ERROR: cannot save the file %s: %s' % (tmp_file, exp)
            rule.add_error(err)
            rule.set_error()
            return
        
        self.logger.debug("MOVING FILE")
        try:
            shutil.move(tmp_file, dest_file)
        except Exception as exp:
            err = 'ERROR: cannot save the file %s: %s' % (dest_file, exp)
            rule.add_error(err)
            rule.set_error()
            return
        self.logger.debug("SAVED TO", dest_file)
        
        # spawn post commands if there are some
        is_ok = rule.launch_post_commands(matching_env)
        if not is_ok:
            return
        
        # We did do the job
        txt = 'The file at %s was download at %s' % (url, dest_file)
        rule.add_fix(txt)
        rule.set_fixed()
        return
