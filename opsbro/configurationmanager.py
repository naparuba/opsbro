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
        'tags'           : {'type': 'list', 'mapto': 'tags'},
        'encryption_key' : {'type': 'string', 'mapto': 'encryption_key'},
        'master_key_priv': {'type': 'string', 'mapto': 'master_key_priv'},
        'master_key_pub' : {'type': 'string', 'mapto': 'master_key_pub'},
        'node-zone'      : {'type': 'string', 'mapto': 'zone'},
        'proxy-node'     : {'type': 'bool', 'mapto': 'is_proxy'},
    }
    
    
    def __init__(self):
        # We will have parameters from:
        # * modules
        # * collectors
        # * agent (main configuration file)
        self.declared_parameters = {'module': {}, 'collector': {}}
        
        # Keep a list of the knowns cfg objects type we will encounter
        # NOTE: will be extend once with the modules types
        self.known_types = set(['check', 'service', 'handler', 'generator', 'zone', 'installor'])
        # For just modules, currently void
        self.modules_known_types = set()
        
        # The cluster starts with defualt parameters, but of course configuration can set them too
        # so we will load them (in the local.yaml file) and give it back to the cluster when it will need it
        self.parameters_for_cluster_from_configuration = {}
        
        # Maybe we did found other variables in the main configuration file or another?
        self.additionnal_variables = {}

        # Cluster parameters
        self.data_dir = os.path.abspath(os.path.join(DEFAULT_DATA_DIR))  # '/var/lib/opsbro/'
        
    
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
    
    
    # For a root.obj_name.key set the parameter_rule
    def declare_parameters(self, root, obj_name, parameter_rules):
        logger.debug('Declare a new parameter: root=%s  obj_name=%s ' % (root, obj_name))
        logger.debug('Parameters: %s' % parameter_rules)
        if root not in self.declared_parameters:
            logger.error('Cannot declare parameters from %s: the root %s is not known (not in %s)' % (obj_name, root, self.declared_parameters.keys()))
            return
        root_entry = self.declared_parameters[root]
        if obj_name in root_entry.keys():
            logger.error('Cannot declare twice parameters from %s.%s: already exiting' % (root, obj_name))
            return
        obj_entry = {}
        root_entry[obj_name] = obj_entry
        for (parameter_name, parameter) in parameter_rules.iteritems():
            logger.debug('Add new parameter: %s.%s.%s : %s' % (root, obj_name, parameter_name, parameter))
            obj_entry[parameter_name] = parameter
    
    
    def dump_parameters(self):
        r = {}
        for (root, parameter_parts) in self.declared_parameters.iteritems():
            r[root] = {}
            for (obj_name, parameter_rules) in parameter_parts.iteritems():
                r[root][obj_name] = {}
                for (parameter_name, parameter) in parameter_rules.iteritems():
                    r[root][obj_name][parameter_name] = parameter.as_json()
        return r
    
    
    # Before we load the cfg dirs, we need to be sure we know all the objects types we will
    # encounter, and especially the ones need by the modules
    def prepare_to_load_cfg_dirs(self):
        modulemanager = self.get_modulemanager()
        
        # and extend with the ones from the modules
        self.modules_known_types = set(modulemanager.get_managed_configuration_types())
        self.known_types.update(self.modules_known_types)
    
    
    def load_cfg_dir(self, cfg_dir, pack_name='', pack_level=''):
        if not os.path.exists(cfg_dir):
            logger.error('ERROR: the configuration directory %s is missing' % cfg_dir)
            return
        for root, dirs, files in os.walk(cfg_dir):
            for name in files:
                fp = os.path.join(root, name)
                logger.debug('Loader: looking for file: %s' % fp)
                if name.endswith('.json') or name.endswith('.yml'):
                    self.open_cfg_file(fp, pack_name=pack_name, pack_level=pack_level)
    
    
    def open_cfg_file(self, fp, pack_name='', pack_level=''):
        is_json = fp.endswith('.json')
        is_yaml = fp.endswith('.yml')
        with open(fp, 'r') as f:
            buf = f.read()
            try:
                if is_json:
                    o = jsoner.loads(buf)
                if is_yaml:
                    o = yamler.loads(buf)
            except Exception, exp:
                logger.error('ERROR: the configuration file %s malformed: %s' % (fp, exp))
                sys.exit(2)
        logger.debug("Configuration, opening file data", o, fp)
        
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
        
        if 'zone' in o:
            zone = o['zone']
            zonemgr = self.get_zonemgr()
            zonemgr.add(zone)
        
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
        
        # grok all others data so we can use them in our checks
        cluster_parameters = self.__class__.cluster_parameters
        for (k, v) in o.iteritems():
            # Manage modules object types
            if k in self.modules_known_types:
                # File modification time
                mod_time = int(os.path.getmtime(fp))
                # file name
                fname = fp
                # file short name
                gname = os.path.splitext(fname)[0]
                # Go import it
                modulemanager = self.get_modulemanager()
                modulemanager.import_managed_configuration_object(k, v, mod_time, fname, gname)
                continue
            
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
            self.load_cfg_dir(dir, pack_name=pname, pack_level=level)


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
