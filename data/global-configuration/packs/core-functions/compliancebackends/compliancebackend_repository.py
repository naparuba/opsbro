from opsbro.systempacketmanager import get_systepacketmgr
from opsbro.compliancemgr import InterfaceComplianceDriver


class RepositoryDriver(InterfaceComplianceDriver):
    name = 'repository'
    
    
    def __init__(self):
        super(RepositoryDriver, self).__init__()
    
    
    # DEBIAN:
    # apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 2930ADAE8CAF5059EE73BB4B58712A2291FA4AD5
    # /etc/apt/sources.list.d/mongodb-org-3.6.list:
    #  7
    #  deb http://repo.mongodb.org/apt/debian wheezy/mongodb-org/3.6 main
    #  8
    #  deb http://repo.mongodb.org/apt/debian jessie/mongodb-org/3.6 main
    # apt-get install -y mongodb-org
    
    # SUSE:
    # rpm --import https://www.mongodb.org/static/pgp/server-3.6.asc
    # zypper addrepo --gpgcheck "https://repo.mongodb.org/zypper/suse/12/mongodb-org/3.6/x86_64/" mongodb
    
    # AMAZON:
    # [mongodb-org-3.6]
    # name=MongoDB Repository
    # baseurl=https://repo.mongodb.org/yum/amazon/2013.03/mongodb-org/3.6/x86_64/
    # gpgcheck=1
    # enabled=1
    # gpgkey=https://www.mongodb.org/static/pgp/server-3.6.asc
    
    # UBUNTU:
    # apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 2930ADAE8CAF5059EE73BB4B58712A2291FA4AD5
    # 16.04:
    # deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu xenial/mongodb-org/3.6 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-3.6.list
    
    # [mongodb-org-3.4]
    # name=MongoDB Repository
    # baseurl=https://repo.mongodb.org/yum/redhat/$releasever/mongodb-org/3.4/x86_64/
    # gpgcheck=1
    # enabled=1
    # gpgkey=https://www.mongodb.org/static/pgp/server-3.4.asc
    # [mongodb-org-3.2]
    # name=MongoDB Repository
    # baseurl=https://repo.mongodb.org/yum/redhat/$releasever/mongodb-org/3.2/x86_64/
    # gpgcheck=1
    # enabled=1
    # gpgkey=https://www.mongodb.org/static/pgp/server-3.2.asc
    # > /etc/yum.repos.d/mongodb-org.repo
    
    # environments:   <- take first to win
    #        - name: centos7  <- for display
    #         if:   "{{collector.system.os.linux.distribution}} == 'ubuntu'"   <- if rule to enable env or not
    #         parameters:
    #           name:
    #           url:
    #           key:
    #           key-server:
    #         - OTHERS
    def launch(self, rule):
        
        mode = rule.get_mode()
        if mode is None:
            return
        
        check_only = (mode == 'audit')
        
        matching_env = rule.get_first_matching_environnement()
        if matching_env is None:
            return
        
        env_name = matching_env.get_name()
        
        did_error = False
        systepacketmgr = get_systepacketmgr()
        
        # Now we can get our parameters
        parameters = matching_env.get_parameters()
        url = parameters.get('url')
        key = parameters.get('key')
        name = parameters.get('name')
        key_server = parameters.get('key-server', '')
        
        if not url or not name:
            err = 'No url or name defined'
            rule.add_error(err)
            rule.set_error()
            return
        
        # STEP1: First key
        if key and key_server:
            try:
                is_set = systepacketmgr.assert_repository_key(key, key_server, check_only=check_only)
                if not is_set:
                    err = 'The key %s from the serveur key %s is not imported' % (key, key_server)
                    rule.add_error(err)
                    rule.set_error()
                    did_error = True
                else:
                    compl = 'The key %s from the server key %s is imported' % (key, key_server)
                    rule.add_compliance(compl)
            except Exception, exp:
                err = 'Cannot import the key %s from the server %s : %s' % (key, key_server, exp)
                rule.add_error(err)
                rule.set_error()
                did_error = True
        
        # STEP2: repository
        try:
            is_repository_set = systepacketmgr.assert_repository(name, url, check_only=check_only)
            if not is_repository_set:
                err = 'The repository named %s is not set' % name
                rule.add_error(err)
                rule.set_error()
                # Nothing more to do, we can exit
                return
        except Exception, exp:
            err = 'Cannot set the repository %s (url=%s) : %s' % (name, url, exp)
            rule.add_error(err)
            rule.set_error()
            return
        
        # If we fail at least one package, exit it
        if did_error:
            rule.set_error()
            return
        
        # spawn post commands if there are some
        is_ok = rule.launch_post_commands(matching_env)
        if not is_ok:
            return
        
        # We did fix all package, cool
        txt = 'Environnement %s: the repository %s is configured' % (env_name, name)
        rule.add_compliance(txt)
        rule.set_compliant()
        return
