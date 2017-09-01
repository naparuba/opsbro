import os
import sys

from opsbro.defaultpaths import DEFAULT_DATA_DIR
from opsbro.log import LoggerFactory
from opsbro.httpdaemon import http_export, response
from opsbro.yamlmgr import yamler
from opsbro.jsonmgr import jsoner
from opsbro.packer import packer

# Global logger for this part
logger = LoggerFactory.create_logger('configuration')


class ConfigurationManager(object):
    # The parameter for the main cluster class is list here, and we will give back to it what we did read in the
    # local.yaml file (one set ones)
    cluster_parameters = {
        'display_name'   : {'type': 'string', 'mapto': 'display_name'},
        'port'           : {'type': 'int', 'mapto': 'port'},
        'datacenters'    : {'type': 'list', 'mapto': 'datacenters'},
        'data'           : {'type': 'path', 'mapto': 'data_dir'},
        'libexec'        : {'type': 'path', 'mapto': 'libexec_dir'},
        'log'            : {'type': 'path', 'mapto': 'log_dir'},
        'lock'           : {'type': 'path', 'mapto': 'lock_path'},
        'socket'         : {'type': 'path', 'mapto': 'socket_path'},
        'log_level'      : {'type': 'string', 'mapto': 'log_level'},
        'bootstrap'      : {'type': 'bool', 'mapto': 'bootstrap'},
        'seeds'          : {'type': 'list', 'mapto': 'seeds'},
        'groups'           : {'type': 'list', 'mapto': 'groups'},
        'encryption_key' : {'type': 'string', 'mapto': 'encryption_key'},
        'master_key_priv': {'type': 'string', 'mapto': 'master_key_priv'},
        'master_key_pub' : {'type': 'string', 'mapto': 'master_key_pub'},
        'node-zone'      : {'type': 'string', 'mapto': 'zone'},
        'proxy-node'     : {'type': 'bool', 'mapto': 'is_proxy'},
    }
    
    
    def __init__(self):
        # Keep a list of the knowns cfg objects type we will encounter
        # NOTE: will be extend once with the modules types
        self.known_types = set(['check', 'service', 'handler', 'generator', 'zone', 'installor'])
        
        # The cluster starts with defualt parameters, but of course configuration can set them too
        # so we will load them (in the local.yaml file) and give it back to the cluster when it will need it
        self.parameters_for_cluster_from_configuration = {}
        
        # Maybe we did found other variables in the main configuration file or another?
        self.additionnal_variables = {}
        
        # Cluster parameters
        self.data_dir = os.path.abspath(os.path.join(DEFAULT_DATA_DIR))  # '/var/lib/opsbro/'
        
        # For each pack, we keep the parameters.yml data
        self.pack_parameters = {}
    
    
    def get_monitoringmgr(self):
        # Import at runtime, to avoid loop
        from opsbro.monitoring import monitoringmgr
        return monitoringmgr
    
    
    def get_handlermgr(self):
        from opsbro.handlermgr import handlermgr
        return handlermgr
    
    
    def get_zonemgr(self):
        from opsbro.zonemanager import zonemgr
        return zonemgr
    
    
    def get_installormgr(self):
        from opsbro.installermanager import installormgr
        return installormgr
    
    
    def get_modulemanager(self):
        from opsbro.modulemanager import modulemanager
        return modulemanager
    
    
    def get_generatormgr(self):
        from opsbro.generatormgr import generatormgr
        return generatormgr
    
    
    def get_detecter(self):
        from opsbro.detectormgr import detecter
        return detecter
    
    
    # the cluster is asking me which parameters are set in the local.yaml file
    def get_parameters_for_cluster_from_configuration(self):
        return self.parameters_for_cluster_from_configuration
    
    
    def load_cfg_dir(self, cfg_dir, load_focus, pack_name='', pack_level=''):
        if not os.path.exists(cfg_dir):
            logger.error('ERROR: the configuration directory %s is missing' % cfg_dir)
            return
        for root, dirs, files in os.walk(cfg_dir):
            for name in files:
                fp = os.path.join(root, name)
                # Only json and yml are interesting
                if not name.endswith('.json') and not name.endswith('.yml'):
                    continue
                logger.debug('Loader: looking for cfg file: %s' % fp)
                # Note: for parameters, if we don't trick the document by adding a first dummy entry
                # at the start of the document, the first key won't be able to have before line comments
                # because they will be put in the document one
                force_document_comment_to_first_entry = False
                if load_focus == 'parameter':
                    force_document_comment_to_first_entry = True
                obj = self.__get_object_from_cfg_file(fp, force_document_comment_to_first_entry=force_document_comment_to_first_entry)
                # agent: pid, log, graoups, etc
                # and zones
                if load_focus == 'agent':
                    self.load_agent_parameters(obj)
                elif load_focus == 'monitoring':
                    self.load_monitoring_object(obj, fp, pack_name=pack_name, pack_level=pack_level)
                elif load_focus == 'generator':
                    self.load_generator_object(obj, fp, pack_name=pack_name, pack_level=pack_level)
                elif load_focus == 'detector':
                    self.load_detector_object(obj, fp, pack_name=pack_name, pack_level=pack_level)
                elif load_focus == 'installor':
                    self.load_installor_object(obj, fp, pack_name=pack_name, pack_level=pack_level)
                elif load_focus == 'parameter':
                    self.load_pack_parameters(obj, pack_name=pack_name, pack_level=pack_level)
                else:
                    raise Exception('Unknown load focus type! %s' % load_focus)
    
    
    def __get_object_from_cfg_file(self, fp, force_document_comment_to_first_entry=False):
        is_json = fp.endswith('.json')
        is_yaml = fp.endswith('.yml')
        with open(fp, 'r') as f:
            buf = f.read()
            try:
                if is_json:
                    o = jsoner.loads(buf)
                elif is_yaml:
                    o = yamler.loads(buf, force_document_comment_to_first_entry=force_document_comment_to_first_entry)
                else:
                    raise Exception('Unknown file extension: %s' % fp)
            except Exception, exp:
                logger.error('ERROR: the configuration file %s malformed: %s' % (fp, exp))
                sys.exit(2)
        logger.debug("Configuration, opening file data", o, fp)
        return o
    
    
    # pid, log & zones
    def load_agent_parameters(self, o):
        if 'zone' in o:
            zone = o['zone']
            zonemgr = self.get_zonemgr()
            zonemgr.add(zone)
        
        # grok all others data so we can use them in our checks
        cluster_parameters = self.__class__.cluster_parameters
        for (k, v) in o.iteritems():
            # check, service, ... are already managed
            if k in self.known_types:
                continue
            
            # if k is not a internal parameters, use it in the cfg_data part
            if k not in cluster_parameters:
                logger.debug("Setting raw variable/value from file: %s=>%s" % (k, v))
                self.additionnal_variables[k] = v
            else:  # cannot be check and service here
                e = cluster_parameters[k]
                _type = e['type']
                mapto = e['mapto']
                if _type == 'int':
                    try:
                        int(v)
                    except ValueError:
                        logger.error('The parameter %s is not an int' % k)
                        return
                elif _type in ['path', 'string']:
                    if not isinstance(v, basestring):
                        logger.error('The parameter %s is not a string' % k)
                        return
                elif _type == 'bool':
                    if not isinstance(v, bool):
                        logger.error('The parameter %s is not a bool' % k)
                        return
                elif _type == 'list':
                    if not isinstance(v, list):
                        logger.error('The parameter %s is not a list' % k)
                        return
                else:
                    logger.error('Unknown parameter type %s' % k)
                    return
                # Save it, and in the cluster point of view (setattr for it)
                self.parameters_for_cluster_from_configuration[mapto] = v
    
    
    # Monitoring objects: check, service and handler
    def load_monitoring_object(self, o, fp, pack_name, pack_level):
        if 'check' in o:
            check = o['check']
            if not isinstance(check, dict):
                logger.error('ERROR: the check from the file %s is not a valid dict' % fp)
                sys.exit(2)
            fname = fp
            mod_time = int(os.path.getmtime(fp))
            cname = os.path.splitext(fname)[0]
            monitoringmgr = self.get_monitoringmgr()
            monitoringmgr.import_check(check, 'file:%s' % fname, cname, mod_time=mod_time, pack_name=pack_name, pack_level=pack_level)
        
        if 'service' in o:
            service = o['service']
            if not isinstance(service, dict):
                logger.error('ERROR: the service from the file %s is not a valid dict' % fp)
                sys.exit(2)
            
            mod_time = int(os.path.getmtime(fp))
            fname = fp
            sname = os.path.splitext(fname)[0]
            monitoringmgr = self.get_monitoringmgr()
            monitoringmgr.import_service(service, 'file:%s' % fname, sname, mod_time=mod_time, pack_name=pack_name, pack_level=pack_level)
        
        if 'handler' in o:
            handler = o['handler']
            
            mod_time = int(os.path.getmtime(fp))
            fname = fp
            hname = os.path.splitext(os.path.basename(fname))[0]
            handlermgr = self.get_handlermgr()
            handlermgr.import_handler(handler, fp, hname, mod_time=mod_time, pack_name=pack_name, pack_level=pack_level)
    
    
    def load_generator_object(self, o, fp, pack_name, pack_level):
        if 'generator' in o:
            generator = o['generator']
            if not isinstance(generator, dict):
                logger.error('ERROR: the generator from the file %s is not a valid dict' % fp)
                sys.exit(2)
            
            mod_time = int(os.path.getmtime(fp))
            fname = fp
            gname = os.path.splitext(fname)[0]
            generatormgr = self.get_generatormgr()
            generatormgr.import_generator(generator, fname, gname, mod_time=mod_time, pack_name=pack_name, pack_level=pack_level)
    
    
    def load_detector_object(self, o, fp, pack_name, pack_level):
        if 'detector' in o:
            detector = o['detector']
            if not isinstance(detector, dict):
                logger.error('ERROR: the detector from the file %s is not a valid dict' % fp)
                sys.exit(2)
            mod_time = int(os.path.getmtime(fp))
            fname = fp
            gname = os.path.splitext(fname)[0]
            detecter = self.get_detecter()
            detecter.import_detector(detector, 'file:%s' % fname, gname, mod_time=mod_time, pack_name=pack_name, pack_level=pack_level)
    
    
    def load_installor_object(self, o, fp, pack_name, pack_level):
        if 'installor' in o:
            installor = o['installor']
            if not isinstance(installor, dict):
                logger.error('ERROR: the installor from the file %s is not a valid dict' % fp)
                sys.exit(2)
            mod_time = int(os.path.getmtime(fp))
            fname = fp
            gname = os.path.splitext(fname)[0]
            installormgr = self.get_installormgr()
            installormgr.import_installor(installor, fname, gname, mod_time=mod_time, pack_name=pack_name, pack_level=pack_level)
    
    
    def load_pack_parameters(self, o, pack_name, pack_level):
        # If not already create entry, we can do it
        if pack_name not in self.pack_parameters:
            self.pack_parameters[pack_name] = {'pack_level': pack_level, 'properties': {}}
        pack_entry = self.pack_parameters[pack_name]
        for (k, v) in o.iteritems():
            pack_entry['properties'][k] = v
    
    
    def get_parameters_from_pack(self, pack_name):
        entry = self.pack_parameters.get(pack_name, None)
        if entry is None:
            return {}
        return entry['properties']
    
    
    def load_modules_from_packs(self):
        modulemanager = self.get_modulemanager()
        pack_directories = packer.give_pack_directories_to_load()
        
        for (pname, level, dir) in pack_directories:
            module_directory = os.path.join(dir, 'module')
            if os.path.exists(module_directory):
                modulemanager.add_module_directory_to_load(module_directory, pname, level)
        
        modulemanager.load_module_sources()
    
    
    def load_configuration_from_packs(self):
        pack_directories = packer.give_pack_directories_to_load()
        
        for (pname, level, dir) in pack_directories:
            # We load the sub directories, but we don't want to have a big mess of objects
            # so must respect for each type
            # dir, load_focus
            _types = [('monitoring', 'monitoring'), ('handlers', 'monitoring'),
                      ('generators', 'generator'), ('parameters', 'parameter'),
                      ('detectors', 'detector'), ('installors', 'installor'),
                      ]
            for sub_dir, load_focus in _types:
                full_sub_dir = os.path.join(dir, sub_dir)
                if os.path.exists(full_sub_dir):
                    self.load_cfg_dir(full_sub_dir, load_focus=load_focus, pack_name=pname, pack_level=level)
    
    
    def load_collectors_from_packs(self):
        # Load at running to avoid endless import loop
        from opsbro.collectormanager import collectormgr
        pack_directories = packer.give_pack_directories_to_load()
        
        for (pname, level, dir) in pack_directories:
            # Now load collectors, an important part for packs :)
            collector_dir = os.path.join(dir, 'collectors')
            if os.path.exists(collector_dir):
                collectormgr.load_directory(collector_dir, pack_name=pname, pack_level=level)
        
        # now collectors class are loaded, load instances from them
        collectormgr.load_all_collectors()
    
    
    ############## Http interface
    # We must create http callbacks in running because
    # we must have the self object
    def export_http(self):
        @http_export('/configuration/parameters')
        def dump_parameters():
            response.content_type = 'application/json'
            r = self.dump_parameters()
            logger.error('DUMP PARAMETERS: %s' % r)
            return r


configmgr = ConfigurationManager()
