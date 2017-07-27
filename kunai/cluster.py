import os
import sys
import socket
import json
import imp
import threading
import time
import hashlib
import signal
import traceback
import cStringIO
import requests as rq

import tempfile
import tarfile
import base64
import shutil
import zlib
import copy

try:
    from Crypto.Cipher import AES
except ImportError:
    AES = None

# DO NOT FORGET:
# sysctl -w net.core.rmem_max=26214400




from kunai.log import LoggerFactory
from kunai.log import logger as raw_logger
from kunai.util import copy_dir, get_public_address, get_server_const_uuid, guess_server_const_uuid
from kunai.threadmgr import threader
from kunai.now import NOW
from kunai.httpclient import HTTP_EXCEPTIONS

from kunai.generator import Generator
# now singleton objects
from kunai.gossip import gossiper
from kunai.kv import kvmgr
from kunai.broadcast import broadcaster
from kunai.httpdaemon import httpdaemon, http_export, response, request, abort, gserver
from kunai.pubsub import pubsub
from kunai.dockermanager import dockermgr
from kunai.encrypter import encrypter, RSA
from kunai.collectormanager import collectormgr
from kunai.info import VERSION
from kunai.stop import stopper
from kunai.evaluater import evaluater
from kunai.detectormgr import detecter
from kunai.packer import packer
from kunai.ts import tsmgr
from kunai.jsonmgr import jsoner
from kunai.yamlmgr import yamler
from kunai.modulemanager import modulemanager
from kunai.zonemanager import zonemgr
from kunai.executer import executer
from kunai.monitoring import monitoringmgr
from kunai.installermanager import installormgr
from kunai.defaultpaths import DEFAULT_LIBEXEC_DIR, DEFAULT_LOCK_PATH, DEFAULT_DATA_DIR, DEFAULT_LOG_DIR

# Global logger for this part
logger = LoggerFactory.create_logger('agent')
logger_gossip = LoggerFactory.create_logger('gossip')


# LIMIT= 4 * math.ceil(math.log10(float(2 + 1)))



class Cluster(object):
    parameters = {
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
    
    
    def __init__(self, port=6768, name='', bootstrap=False, seeds='', tags='', cfg_dir='', libexec_dir=''):
        self.set_exit_handler()
        
        # Launch the now-update thread
        NOW.launch()
        
        # This will be the place where we will get our configuration data
        self.cfg_data = {}
        
        self.generators = {}
        self.detectors = {}
        self.handlers = {}
        
        # Some default value that can be erased by the
        # main configuration file
        # By default no encryption
        self.encryption_key = ''
        # Same for public/priv for the master fucking key
        self.master_key_priv = ''  # Paths
        self.master_key_pub = ''
        self.mfkey_priv = None  # real key objects
        self.mfkey_pub = None
        
        self.port = port
        self.name = name
        self.display_name = ''
        self.hostname = socket.gethostname()
        if not self.name:
            self.name = '%s' % self.hostname
        tags = [s.strip() for s in tags.split(',') if s.strip()]
        
        self.bootstrap = bootstrap
        self.seeds = [s.strip() for s in seeds.split(',')]
        self.zone = ''
        
        self.addr = get_public_address()
        self.listening_addr = '0.0.0.0'
        
        self.data_dir = os.path.abspath(os.path.join(DEFAULT_DATA_DIR))  # '/var/lib/kunai/')
        self.log_dir = DEFAULT_LOG_DIR  # '/var/log/kunai'
        self.lock_path = DEFAULT_LOCK_PATH  # '/var/run/kunai.lock'
        self.libexec_dir = DEFAULT_LIBEXEC_DIR  # '/var/lib/kunai/libexec'
        self.socket_path = '$data$/kunai.sock'
        
        self.log_level = 'INFO'
        
        # Let the modules know about the daemon object
        modulemanager.set_daemon(self)
        
        # save the known types for the configuration
        self.known_types = ['check', 'service', 'handler', 'generator', 'zone', 'installor']
        # and extend with the ones from the modules
        self.modules_known_types = modulemanager.get_managed_configuration_types()
        self.known_types.extend(self.modules_known_types)
        
        # Now look at the cfg_dir part
        if cfg_dir:
            self.cfg_dir = os.path.abspath(cfg_dir)
        else:
            self.cfg_dir = DEFAULT_LOG_DIR
        
        if not os.path.exists(self.cfg_dir):
            logger.error('Configuration directory [%s] is missing' % self.cfg_dir)
            sys.exit(2)
        
        # We need the main cfg_directory
        self.load_cfg_dir(self.cfg_dir)
        
        # We can start with a void data dir
        if not os.path.exists(self.data_dir):
            os.mkdir(self.data_dir)
        
        # We can start with a void log dir too
        if not os.path.exists(self.log_dir):
            os.mkdir(self.log_dir)
        
        # Then we will need to look at other directories, list from
        # * global-confugration = comon to all nodes
        # * local-configuration = on this specific node
        self.global_configuration = os.path.join(self.data_dir, 'global-configuration')
        self.zone_configuration = os.path.join(self.data_dir, 'zone-configuration')
        self.local_configuration = os.path.join(self.data_dir, 'local-configuration')
        
        # Ok let's load global configuration
        self.load_cfg_dir(self.global_configuration)
        # then zone one
        self.load_cfg_dir(self.zone_configuration)
        # and then local one
        self.load_cfg_dir(self.local_configuration)
        
        # Configure the logger with its new level if need
        raw_logger.setLevel(self.log_level)
        
        # For the path inside the configuration we must
        # string replace $data$ by the good value if it's set
        parameters = self.__class__.parameters
        for (k, d) in parameters.iteritems():
            if d['type'] == 'path':
                mapto = d['mapto']
                v = getattr(self, mapto).replace('$data$', self.data_dir)
                setattr(self, mapto, v)
        
        # Default some parameters, like is_proxy
        if not hasattr(self, 'is_proxy'):
            self.is_proxy = False
        
        # open the log file
        raw_logger.load(self.log_dir, self.name)
        raw_logger.export_http()
        
        # Look if our encryption key is valid or not
        if self.encryption_key:
            if AES is None:
                logger.error('You set an encryption key but cannot import python-crypto module, please install it. Exiting.')
                sys.exit(2)
            try:
                self.encryption_key = base64.b64decode(self.encryption_key)
            except ValueError:
                logger.warning('The encryption key is invalid, not in base64 format')
                # todo: exit or no exit?
        # and load the encryption key in the global encrypter object
        encrypter.load(self.encryption_key)
        
        # Same for master fucking key PRIVATE
        if self.master_key_priv:
            if not os.path.isabs(self.master_key_priv):
                self.master_key_priv = os.path.join(self.cfg_dir, self.master_key_priv)
            if not os.path.exists(self.master_key_priv):
                logger.error('Cannot find the master key private file at %s' % self.master_key_priv)
            else:
                if RSA is None:
                    logger.error('You set a master private key but but cannot import python-rsa module, please install it. Exiting.')
                    sys.exit(2)
                
                with open(self.master_key_priv, 'r') as f:
                    buf = f.read()
                try:
                    self.mfkey_priv = RSA.PrivateKey.load_pkcs1(buf)
                except Exception, exp:
                    logger.error('Invalid master private key at %s. (%s) Exiting.' % (self.master_key_priv, exp))
                    sys.exit(2)
                logger.info('Master private key file %s is loaded' % self.master_key_priv)
        
        # Same for master fucking key PUBLIC
        if self.master_key_pub:
            if not os.path.isabs(self.master_key_pub):
                self.master_key_pub = os.path.join(self.cfg_dir, self.master_key_pub)
            if not os.path.exists(self.master_key_pub):
                logger.error('Cannot find the master key public file at %s' % self.master_key_pub)
            else:
                if RSA is None:
                    logger.error('You set a master public key but but cannot import python-crypto module, please install it. Exiting.')
                    sys.exit(2)
                # let's try to open the key so :)
                with open(self.master_key_pub, 'r') as f:
                    buf = f.read()
                try:
                    self.mfkey_pub = RSA.PublicKey.load_pkcs1(buf)
                except Exception, exp:
                    logger.error('Invalid master public key at %s. (%s) Exiting.' % (self.master_key_pub, exp))
                    sys.exit(2)
                logger.info('Master public key file %s is loaded' % self.master_key_pub)
        
        # Open the retention data about our previous runs
        # but some are specific to this agent uuid
        self.server_key_file = os.path.join(self.data_dir, 'server.key')
        self.last_alive_file = os.path.join(self.data_dir, 'last_alive')
        self.hostname_file = os.path.join(self.data_dir, 'last_hostname')
        self.zone_file = os.path.join(self.data_dir, 'current_zone')
        
        # Our cluster need a unique uuid, so try to guess a unique one from Hardware
        # To get a UUID that will be unique to this instance:
        # * If there is a hardware one, use it, whatever the hostname is or the local
        #   file are saying
        # * If there is not, then try to look at local file, and take if :
        #     * we have the same hostname than before
        #     * if we did change the hostname then recreate one
        self.uuid = get_server_const_uuid()
        if not self.uuid:  # if the hardware one is not valid, try to look at previous
            # first look if previous hostname was the same as before,
            # because maybe we are a VM that just did change/clone
            last_hostname = ''
            if os.path.exists(self.hostname_file):
                with open(self.hostname_file, 'r') as f:
                    last_hostname = f.read().strip()
            
            if self.hostname == last_hostname and os.path.exists(self.server_key_file):
                with open(self.server_key_file, 'r') as f:
                    self.uuid = f.read()
                logger.log("KEY: %s loaded from previous key file %s" % (self.uuid, self.server_key_file))
            else:
                # Ok no way to get from past, so try to guess the more stable possible, and if not ok, give me random stuff
                self.uuid = guess_server_const_uuid()
        
        # now save the key
        with open(self.server_key_file, 'w') as f:
            f.write(self.uuid)
        logger.log("KEY: %s saved to the key file %s" % (self.uuid, self.server_key_file))
        
        # we can save the current hostname
        with open(self.hostname_file, 'w') as f:
            f.write(self.hostname)
        
        # Now we can open specific agent files
        self.agent_instance_dir = os.path.join(self.data_dir, self.uuid)
        if not os.path.exists(self.agent_instance_dir):
            os.mkdir(self.agent_instance_dir)
        self.incarnation_file = os.path.join(self.agent_instance_dir, 'incarnation')
        self.nodes_file = os.path.join(self.agent_instance_dir, 'nodes.json')
        self.check_retention = os.path.join(self.agent_instance_dir, 'checks.dat')
        self.service_retention = os.path.join(self.agent_instance_dir, 'services.dat')
        self.collector_retention = os.path.join(self.agent_instance_dir, 'collectors.dat')
        
        # Now load nodes to do not start from zero, but not ourselves (we will regenerate it with a new incarnation number and
        # up to date info)
        if os.path.exists(self.nodes_file):
            with open(self.nodes_file, 'r') as f:
                nodes = json.loads(f.read())
                # If we were in nodes, remove it, we will refresh it
                if self.uuid in nodes:
                    del nodes[self.uuid]
        else:
            nodes = {}
        # We must protect the nodes with a lock
        nodes_lock = threading.RLock()
        
        # Load some files, like the old incarnation file
        if os.path.exists(self.incarnation_file):
            with open(self.incarnation_file, 'r') as f:
                self.incarnation = json.loads(f.read())
                self.incarnation += 1
        else:
            self.incarnation = 0
        
        # Load check and service retention as they are filled
        # collectors will wait a bit
        # We can give the cfg dir to the monitoring part, to allow it to manage/update
        # json files
        monitoringmgr.load(self.cfg_dir, self.cfg_data)
        monitoringmgr.load_check_retention(self.check_retention)
        monitoringmgr.load_service_retention(self.service_retention)
        
        # Now init the kv backend and allow it to load its database
        kvmgr.init(self.data_dir)
        
        self.last_retention_write = time.time()
        
        # we keep the data about the last time we were launch, to detect crash and such things
        if os.path.exists(self.last_alive_file):
            with open(self.last_alive_file, 'r') as f:
                self.last_alive = json.loads(f.read())
        else:
            self.last_alive = int(time.time())
        
        # Load previous zone if available
        if os.path.exists(self.zone_file):
            with open(self.zone_file, 'r') as f:
                self.zone = f.read().strip()
        
        # Try to clean libexec and configuration directories
        self.libexec_dir = libexec_dir
        if self.libexec_dir:
            self.libexec_dir = os.path.abspath(self.libexec_dir)
        
        self.configuration_dir = self.cfg_dir
        if self.configuration_dir:
            self.configuration_dir = os.path.abspath(self.configuration_dir)
        
        # Our main events dict, should not be too old or we will delete them
        self.events_lock = threading.RLock()
        self.events = {}
        self.max_event_age = 30
        
        # We will receive a list of path to update for libexec, and we will manage them
        # in athread so the upd thread is not blocking
        self.libexec_to_update = []
        self.configuration_to_update = []
        threader.create_and_launch(self.do_update_libexec_cfg_thread, name='Checks directory (libexec) updates', essential=True, part='agent')
        
        # by default do not launch timeserie listeners
        
        # Launch a thread that will reap all put key asked by the udp
        threader.create_and_launch(kvmgr.put_key_reaper, name='key reaper', essential=True, part='key-value')
        
        # Load all collectors globaly
        collectormgr.load_collectors(self.cfg_data)
        # and configuration ones from local and global configuration
        self.load_packs(self.local_configuration)
        self.load_packs(self.global_configuration)
        # and their last data
        self.load_collector_retention()
        collectormgr.export_http()
        
        # Open our TimeSerie manager and open the database in data_dir/ts
        tsmgr.tsb.load(self.data_dir)
        tsmgr.tsb.export_http()
        
        # Load key into the executor
        executer.load(self.mfkey_pub, self.mfkey_priv)
        executer.export_http()
        
        # the evaluater need us to grok into our cfg_data and such things
        evaluater.load(self.cfg_data)
        evaluater.export_http()
        
        # Load docker thing if possible
        dockermgr.export_http()
        dockermgr.launch()
        
        # Our main object for gossip managment
        gossiper.init(nodes, nodes_lock, self.addr, self.port, self.name, self.display_name, self.incarnation, self.uuid, tags, self.seeds, self.bootstrap, self.zone, self.is_proxy)
        
        # About detecting tags and such things
        detecter.load(self)
        detecter.export_http()
        
        # Let the modules prepare themselve
        modulemanager.prepare()
        modulemanager.export_http()
        
        # We can now link checks/services based on what we have
        monitoringmgr.link_checks()
        monitoringmgr.link_services()
        # Export checks/services http interface
        monitoringmgr.export_http()
        
        # Also run installor part, as it need other part to be runs
        installormgr.export_http()
        
        # get the message in a pub-sub way
        pubsub.sub('manage-message', self.manage_message_pub)
    
    
    def load_cfg_dir(self, cfg_dir):
        if not os.path.exists(cfg_dir):
            logger.error('ERROR: the configuration directory %s is missing' % cfg_dir)
            sys.exit(2)
        for root, dirs, files in os.walk(cfg_dir):
            for name in files:
                fp = os.path.join(root, name)
                logger.log('Loader: looking for file: %s' % fp)
                if name.endswith('.json'):
                    self.open_cfg_file(fp)
                if name == 'module.py':
                    # dir name as module name part
                    dname = os.path.split(root)[1]
                    # Load this module.py file
                    m = imp.load_source('__module_' + dname, fp)
                    logger.debug("Loader user module", m, "from", fp)
    
    
    def load_packs(self, root_dir):
        logger.debug('Loading packs directory')
        pack_dir = os.path.join(root_dir, 'packs')
        if not os.path.exists(pack_dir):
            logger.debug('ERROR: the pack directory %s is missing' % pack_dir)
            return
        sub_dirs = [os.path.join(pack_dir, dname) for dname in os.listdir(pack_dir) if
                    os.path.isdir(os.path.join(pack_dir, dname))]
        logger.debug('Loading packs directories : %s' % sub_dirs)
        # Look at collectors
        for pname in sub_dirs:
            # First load meta data from the package.json file (if present)
            package_pth = os.path.join(pname, 'package.json')
            pack_name = pname  # by default take the directory name
            if os.path.exists(package_pth):
                try:
                    with open(package_pth, 'r') as f:
                        package_buf = f.read()
                        package = json.loads(package_buf)
                        if not isinstance(package, dict):
                            raise Exception('Package.json file %s is not a valid dict object' % package_pth)
                        pack_name = packer.load_package(package, package_pth)
                except Exception, exp:  # todo: more precise catch? I think so
                    logger.error('Cannot load package %s: %s' % (package_pth, exp))
            
            # Now load collectors, an important part for packs :)
            collector_dir = os.path.join(pname, 'collectors')
            if os.path.exists(collector_dir):
                collectormgr.load_directory(collector_dir, pack_name=pack_name)
        
        # now collectors class are loaded, load instances from them
        collectormgr.load_all_collectors()
    
    
    def open_cfg_file(self, fp):
        with open(fp, 'r') as f:
            buf = f.read()
            try:
                o = json.loads(buf)
            except Exception, exp:
                logger.log('ERROR: the configuration file %s malformed: %s' % (fp, exp))
                sys.exit(2)
        if not isinstance(o, dict):
            logger.log('ERROR: the configuration file %s content is not a valid dict' % fp)
            sys.exit(2)
        logger.debug("Configuration, opening file data", o, fp)
        
        if 'check' in o:
            check = o['check']
            if not isinstance(check, dict):
                logger.log('ERROR: the check from the file %s is not a valid dict' % fp)
                sys.exit(2)
            print fp
            fname = fp[len(self.cfg_dir) + 1:]
            mod_time = int(os.path.getmtime(fp))
            cname = os.path.splitext(fname)[0]
            monitoringmgr.import_check(check, 'file:%s' % fname, cname, mod_time=mod_time)
        
        if 'service' in o:
            service = o['service']
            if not isinstance(service, dict):
                logger.log('ERROR: the service from the file %s is not a valid dict' % fp)
                sys.exit(2)
            
            mod_time = int(os.path.getmtime(fp))
            fname = fp[len(self.cfg_dir) + 1:]
            sname = os.path.splitext(fname)[0]
            monitoringmgr.import_service(service, 'file:%s' % fname, sname, mod_time=mod_time)
        
        if 'handler' in o:
            handler = o['handler']
            if not isinstance(handler, dict):
                logger.log('ERROR: the handler from the file %s is not a valid dict' % fp)
                sys.exit(2)
            
            mod_time = int(os.path.getmtime(fp))
            fname = fp[len(self.cfg_dir) + 1:]
            hname = os.path.splitext(fname)[0]
            self.import_handler(handler, 'file:%s' % hname, hname, mod_time=mod_time)
        
        if 'generator' in o:
            generator = o['generator']
            if not isinstance(generator, dict):
                logger.log('ERROR: the generator from the file %s is not a valid dict' % fp)
                sys.exit(2)
            
            mod_time = int(os.path.getmtime(fp))
            fname = fp
            gname = os.path.splitext(fname)[0]
            self.import_generator(generator, fname, gname, mod_time=mod_time)
        
        if 'detector' in o:
            detector = o['detector']
            if not isinstance(detector, dict):
                logger.log('ERROR: the detector from the file %s is not a valid dict' % fp)
                sys.exit(2)
            mod_time = int(os.path.getmtime(fp))
            fname = fp[len(self.cfg_dir) + 1:]
            gname = os.path.splitext(fname)[0]
            self.import_detector(detector, 'file:%s' % fname, gname, mod_time=mod_time)
        
        if 'zone' in o:
            zone = o['zone']
            if not isinstance(zone, dict):
                logger.log('ERROR: the zone from the file %s is not a valid dict' % fp)
                sys.exit(2)
            zonemgr.add(zone)
        
        if 'installor' in o:
            installor = o['installor']
            if not isinstance(installor, dict):
                logger.log('ERROR: the installor from the file %s is not a valid dict' % fp)
                sys.exit(2)
            mod_time = int(os.path.getmtime(fp))
            fname = fp
            gname = os.path.splitext(fname)[0]
            installormgr.import_installor(installor, fname, gname, mod_time=mod_time)
        
        # grok all others data so we can use them in our checks
        parameters = self.__class__.parameters
        for (k, v) in o.iteritems():
            # Manage modules object types
            if k in self.modules_known_types:
                # File modification time
                mod_time = int(os.path.getmtime(fp))
                # file name
                fname = fp[len(self.cfg_dir) + 1:]
                # file short name
                gname = os.path.splitext(fname)[0]
                # Go import it
                modulemanager.import_managed_configuration_object(k, v, mod_time, fname, gname)
                continue
            # check, service, ... are already managed
            if k in self.known_types:
                continue
            # if k is not a internal parameters, use it in the cfg_data part
            if k not in parameters:
                logger.debug("SETTING RAW VALUE", k, v)
                self.cfg_data[k] = v
            else:  # cannot be check and service here
                e = parameters[k]
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
                # It's valid, I set it :)
                setattr(self, mapto, v)
    
    
    def import_handler(self, handler, fr, hname, mod_time=0):
        handler['from'] = fr
        handler['name'] = handler['id'] = hname
        if 'notes' not in handler:
            handler['notes'] = ''
        handler['modification_time'] = mod_time
        if 'severities' not in handler:
            handler['severities'] = ['ok', 'warning', 'critical', 'unknown']
        # look at types now
        if 'type' not in handler:
            handler['type'] = 'none'
        _type = handler['type']
        if _type == 'mail':
            if 'email' not in handler:
                handler['email'] = 'root@localhost'
        
        # Add it into the list
        self.handlers[handler['id']] = handler
    
    
    # Generators will create files based on templates from
    # data and nodes after a change on a node
    def import_generator(self, generator, fr, gname, mod_time=0):
        generator['from'] = fr
        generator['name'] = generator['id'] = gname
        if 'notes' not in generator:
            generator['notes'] = ''
        if 'apply_on' not in generator:
            generator['apply_on'] = generator['name']
        
        for prop in ['path', 'template']:
            if prop not in generator:
                logger.warning('Bad generator, missing property %s in the generator %s' % (prop, gname))
                return
        # Template must be from configuration path
        gen_base_dir = os.path.dirname(fr)
        
        generator['template'] = os.path.normpath(os.path.join(gen_base_dir, generator['template']))
        # and path must be a abs path
        generator['path'] = os.path.abspath(generator['path'])
        
        # We will try not to hummer the generator
        generator['modification_time'] = mod_time
        
        for k in ['partial_start', 'partial_end']:
            if k not in generator:
                generator[k] = ''
        
        generator['if_partial_missing'] = generator.get('if_partial_missing', '')
        if generator['if_partial_missing'] and generator['if_partial_missing'] not in ['append']:
            logger.error('Generator %s if_partial_missing property is not valid: %s' % (generator['name'], generator['if_partial_missing']))
            return
        
        # Add it into the generators list
        self.generators[generator['id']] = generator
    
    
    # Detectors will run rules based on collectors and such things, and will tag the local node
    # if the rules are matching
    def import_detector(self, detector, fr, gname, mod_time=0):
        detector['from'] = fr
        detector['name'] = detector['id'] = gname
        if 'notes' not in detector:
            detector['notes'] = ''
        if 'apply_on' not in detector:
            detector['apply_on'] = detector['name']
        
        for prop in ['tags', 'apply_if']:
            if prop not in detector:
                logger.warning('Bad detector, missing property %s in the detector %s' % (prop, gname))
                return
        if not isinstance(detector['tags'], list):
            logger.warning('Bad detector, tags is not a list in the detector %s' % gname)
            return
        
        # We will try not to hummer the detector
        detector['modification_time'] = mod_time
        
        # Do not lunach too much
        detector['last_launch'] = 0
        
        # By default do not match
        detector['do_apply'] = False
        
        # Add it into the detectors list
        self.detectors[detector['id']] = detector
    
    
    # Load raw results of collectors, and give them to the
    # collectormgr that will know how to load them :)
    def load_collector_retention(self):
        if not os.path.exists(self.collector_retention):
            return
        
        logger.log('Collectors loading collector retention file %s' % self.collector_retention)
        with open(self.collector_retention, 'r') as f:
            loaded = json.loads(f.read())
            collectormgr.load_retention(loaded)
        logger.log('Collectors loaded retention file %s' % self.collector_retention)
    
    
    # What to do when we receive a signal from the system
    def manage_signal(self, sig, frame):
        logger.log("I'm process %d and I received signal %s" % (os.getpid(), str(sig)))
        if sig == signal.SIGUSR1:  # if USR1, ask a memory dump
            logger.log('MANAGE USR1')
        elif sig == signal.SIGUSR2:  # if USR2, ask objects dump
            logger.log('MANAGE USR2')
        else:  # Ok, really ask us to die :)
            self.set_interrupted()
    
    
    # Callback for objects that want us to stop in a clean way
    def set_interrupted(self):
        # and the global object too
        stopper.interrupted = True
    
    
    def set_exit_handler(self):
        # First register the self.interrupted in the pubsub call
        # interrupt
        pubsub.sub('interrupt', self.set_interrupted)
        
        func = self.manage_signal
        if os.name == "nt":
            try:
                import win32api
                
                win32api.SetConsoleCtrlHandler(func, True)
            except ImportError:
                version = ".".join(map(str, sys.version_info[:2]))
                raise Exception("pywin32 not installed for Python " + version)
        else:
            for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGUSR1, signal.SIGUSR2):
                signal.signal(sig, func)
    
    
    def launch_check_thread(self):
        self.check_thread = threader.create_and_launch(monitoringmgr.do_check_thread, name='Checks executions', essential=True, part='monitoring')
    
    
    def launch_collector_thread(self):
        self.collector_thread = threader.create_and_launch(collectormgr.do_collector_thread, name='Collector scheduling', essential=True, part='collector')
    
    
    def launch_generator_thread(self):
        self.generator_thread = threader.create_and_launch(self.do_generator_thread, name='Generator scheduling', essential=True, part='generator')
    
    
    def launch_detector_thread(self):
        self.detector_thread = threader.create_and_launch(detecter.do_detector_thread, name='Detector scheduling', essential=True, part='detector')
    
    
    def launch_installor_thread(self):
        threader.create_and_launch(installormgr.do_installer_thread, name='Installor scheduling', essential=True, part='installor')
    
    
    def launch_replication_backlog_thread(self):
        self.replication_backlog_thread = threader.create_and_launch(kvmgr.do_replication_backlog_thread, name='Replication backlog', essential=True, part='key-value')
    
    
    def launch_replication_first_sync_thread(self):
        self.replication_first_sync_thread = threader.create_and_launch(self.do_replication_first_sync_thread, name='First replication synchronization', essential=True, part='key-value')
    
    
    def launch_listeners(self):
        self.udp_thread = threader.create_and_launch(self.launch_udp_listener, name='UDP listener', essential=True, part='gossip')
        self.tcp_thread = threader.create_and_launch(self.launch_tcp_listener, name='Http backend', essential=True, part='agent')
        
        # Launch modules threads
        modulemanager.launch()
    
    
    def launch_udp_listener(self):
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        self.udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)  # Allow Broadcast (useful for node discovery)
        logger.info("OPENING UDP", self.addr)
        self.udp_sock.bind((self.listening_addr, self.port))
        logger.log("UDP port open", self.port)
        while not stopper.interrupted:
            try:
                data, addr = self.udp_sock.recvfrom(65535)  # buffer size is 1024 bytes
            except socket.timeout:
                continue  # nothing in few seconds? just loop again :)
            
            # No data? bail out :)
            if len(data) == 0:
                logger_gossip.debug("UDP: received void message from ", addr)
                continue
            
            # Look if we use encryption
            data = encrypter.decrypt(data)
            # Maybe the decryption failed?
            if data == '':
                logger_gossip.debug("UDP: received message with bad encryption key from ", addr)
                continue
            logger_gossip.debug("UDP: received message:", data, 'from', addr)
            # Ok now we should have a json to parse :)
            try:
                raw = json.loads(data)
            except ValueError:  # garbage
                logger_gossip.debug("UDP: received message that is not valid json:", data, 'from', addr)
                continue
            
            if isinstance(raw, list):
                messages = raw
            else:
                messages = [raw]
            for m in messages:
                if not isinstance(m, dict):
                    continue
                t = m.get('type', None)
                if t is None:
                    continue
                if t == 'ping':
                    gossiper.manage_ping_message(m, addr)
                elif t == 'ping-relay':
                    gossiper.manage_ping_relay_message(m, addr)
                elif t == 'detect-ping':
                    gossiper.manage_detect_ping_message(m, addr)
                elif t == '/kv/put':
                    k = m['k']
                    v = m['v']
                    fw = m.get('fw', False)
                    # For perf data we allow the udp send
                    kvmgr.put_key(k, v, allow_udp=True, fw=fw)
                elif t == '/ts/new':
                    key = m.get('key', '')
                    # Skip this message for classic nodes
                    if key == '':
                        continue
                    # if TS do not have it, it will propagate it
                    tsmgr.set_name_if_unset(key)
                # Someone is asking us a challenge, ok do it
                elif t == '/exec/challenge/ask':
                    executer.manage_exec_challenge_ask_message(m, addr)
                elif t == '/exec/challenge/return':
                    executer.manage_exec_challenge_return_message(m, addr)
                else:
                    self.manage_message(m)
    
    
    # TODO: SPLIT into modules :)
    def launch_tcp_listener(self):
        
        @http_export('/agent/info')
        def get_info():
            response.content_type = 'application/json'
            r = {'logs'      : raw_logger.get_errors(), 'pid': os.getpid(), 'name': self.name, 'display_name': self.display_name,
                 'port'      : self.port, 'addr': self.addr, 'socket': self.socket_path, 'zone': gossiper.zone,
                 'uuid'      : gossiper.uuid,
                 'threads'   : threader.get_info(),
                 'version'   : VERSION, 'tags': gossiper.tags,
                 'docker'    : dockermgr.get_info(),
                 'collectors': collectormgr.get_info(),
                 'kv'        : kvmgr.get_info(),
                 }
            
            # Update the infos with modules ones
            mod_infos = modulemanager.get_infos()
            r.update(mod_infos)
            
            r['httpservers'] = {}
            # Look at both http servers
            for (k, server) in gserver.iteritems():
                if server is None:
                    r['httpservers'][k] = None
                    continue
                # if available get stats (some old cherrypy versions do not have them, like in debian 6)
                s = getattr(server, 'stats', None)
                if not s:
                    continue
                nb_threads = s['Threads'](s)
                idle_threads = s['Threads Idle'](s)
                q = s['Queue'](s)
                r['httpservers'][k] = {'nb_threads': nb_threads, 'idle_threads': idle_threads, 'queue': q}
            
            return r
        
        
        @http_export('/agent/generators')
        def agent_generators():
            response.content_type = 'application/json'
            logger.debug("/agent/generators is called")
            return self.generators
        
        
        @http_export('/agent/generators/:gname#.+#')
        def agent_generator(gname):
            response.content_type = 'application/json'
            logger.debug("/agent/generator is called for %s" % gname)
            if gname not in self.generators:
                return abort(404, 'generator not found')
            return self.generators[gname]
        
        
        @http_export('/agent/propagate/libexec', method='GET')
        def propage_libexec():
            logger.debug("Call to propagate-configuraion")
            if not os.path.exists(self.libexec_dir):
                abort(400, 'Libexec directory is not existing')
            all_files = [os.path.join(dp, f) for dp, dn, filenames in os.walk(os.path.abspath(self.libexec_dir)) for f
                         in filenames]
            for fname in all_files:
                path = fname[len(os.path.abspath(self.libexec_dir)) + 1:]
                # first try to open the path and get a hash of the local file
                f = open(fname, 'rb')
                _hash = hashlib.sha1(f.read()).hexdigest()
                f.close()
                logger.debug("propagate saving FILE %s into the KV space" % fname)
                f = tempfile.TemporaryFile()
                
                with tarfile.open(fileobj=f, mode="w:gz") as tar:
                    tar.add(fname, arcname=path)
                f.seek(0)
                zbuf = f.read()
                f.close()
                buf64 = base64.b64encode(zbuf)
                
                logger.debug("propagate READ A %d file %s and compressed into a %d one..." % (len(zbuf), path, len(buf64)))
                key = '__libexec/%s' % path
                
                kvmgr.put_key(key, buf64)
                
                payload = {'type': 'libexec', 'path': path, 'hash': _hash}
                self.stack_event_broadcast(payload)
        
        
        @http_export('/agent/propagate/configuration', method='GET')
        def propage_configuration():
            logger.debug("propagate conf call TO PROPAGATE CONFIGURATION")
            if not os.path.exists(self.configuration_dir):
                abort(400, 'Configuration directory is not existing')
            all_files = [os.path.join(dp, f) for dp, dn, filenames in os.walk(os.path.abspath(self.configuration_dir))
                         for f in filenames]
            # we keep a list of (path, sha1) combo for the
            ok_files = []
            for fname in all_files:
                path = fname[len(os.path.abspath(self.configuration_dir)) + 1:]
                # Do not send our local.json, it's local, not global!
                if path == 'local.json':
                    continue
                # first try to open the path and get a hash of the local file
                f = open(fname, 'rb')
                _hash = hashlib.sha1(f.read()).hexdigest()
                f.close()
                
                # save this entry
                ok_files.append((path, _hash))
                
                logger.debug("propagate conf SAVING FILE %s into the KV space" % fname)
                # get a tar for this file, and base64 it
                f = tempfile.TemporaryFile()
                with tarfile.open(fileobj=f, mode="w:gz") as tar:
                    tar.add(fname, arcname=path)
                f.seek(0)
                zbuf = f.read()
                f.close()
                buf64 = base64.b64encode(zbuf)
                
                print "READ A %d file %s and compressed into a %d one..." % (len(zbuf), path, len(buf64))
                key = '__configuration/%s' % path
                print "READ PUT KEY", key
                kvmgr.put_key(key, buf64)
                
                payload = {'type': 'configuration', 'path': path, 'hash': _hash}
                self.stack_event_broadcast(payload)
            
            ok_files = [fname[len(os.path.abspath(self.configuration_dir)) + 1:] for fname in all_files]
            logger.debug("propagate configuration All files", ok_files)
            j = json.dumps(ok_files)
            zj = zlib.compress(j, 9)
            zj64 = base64.b64encode(zj)
            kvmgr.put_key('__configuration', zj64)
            payload = {'type': 'configuration-cleanup'}
            self.stack_event_broadcast(payload)
        
        
        @http_export('/configuration/update', method='PUT')
        def update_configuration():
            value = request.body.getvalue()
            logger.debug("HTTP: configuration update put %s" % (value))
            try:
                update = json.loads(value)
            except ValueError:  # bad json...
                return abort(400, 'Bad json data')
            local_file = os.path.join(self.configuration_dir, 'local.json')
            j = {}
            with open(local_file, 'r') as f:
                buf = f.read()
                j = json.loads(buf)
            j.update(update)
            # Now save it
            with open(local_file, 'w') as f:
                f.write(json.dumps(j, sort_keys=True, indent=4))
            # Load the data we can
            self.open_cfg_file(local_file)
            logger.debug('HTTP configuration update, now got %s' % j)
            return
        
        
        @http_export('/configuration', method='GET')
        def get_configuration():
            response.content_type = 'application/json'
            logger.debug("HTTP: configuration get ")
            local_file = os.path.join(self.configuration_dir, 'local.json')
            
            with open(local_file, 'r') as f:
                buf = f.read()
                j = json.loads(buf)
            return j
        
        
        @http_export('/agent/zone', method='PUT', protected=True)
        def post_zone():
            response.content_type = 'application/json'
            
            nzone = request.body.getvalue()
            logger.debug("HTTP: /agent/zone put %s" % (nzone))
            gossiper.change_zone(nzone)
            with open(self.zone_file, 'w') as f:
                f.write(nzone)
            return json.dumps(True)
        
        
        @http_export('/stop', protected=True)
        def do_stop():
            pubsub.pub('interrupt')
            return 'OK'
        
        
        @http_export('/debug/memory')
        def do_memory_dump():
            response.content_type = 'application/json'
            from meliae import scanner
            p = '/tmp/memory-%s' % self.name
            scanner.dump_all_objects(p)
            return json.dumps(p)
        
        
        self.external_http_thread = threader.create_and_launch(httpdaemon.run, name='External HTTP', args=(self.listening_addr, self.port, ''), essential=True, part='agent')
        # Create the internal http thread
        # on unix, use UNIXsocket
        if os.name != 'nt':
            self.internal_http_thread = threader.create_and_launch(httpdaemon.run, name='Internal HTTP', args=('', 0, self.socket_path,), essential=True, part='agent')
        else:  # ok windows, I look at you, really
            self.internal_http_thread = threader.create_and_launch(httpdaemon.run, name='Internal HTTP', args=('127.0.0.1', 6770, '',), essential=True, part='gossip')
    
    
    # launch metric based listeners and backend
    def start_ts_listener(self):
        tsmgr.start_threads()
    
    
    # The first sync thread will ask to our replicats for their lately changed value
    # and we will get the key/value from it
    def do_replication_first_sync_thread(self):
        if 'kv' not in gossiper.tags:
            logger.log('SYNC no need, I am not a KV node')
            return
        logger.log('SYNC thread launched')
        # We will look until we found a repl that answer us :)
        while True:
            repls = kvmgr.get_my_replicats()
            for repluuid in repls:
                repl = gossiper.get(repluuid)
                # Maybe someone just delete my node, if so skip it
                if repl is None:
                    continue
                addr = repl['addr']
                port = repl['port']
                logger.log('SYNC try to sync from %s since the time %s' % (repl['name'], self.last_alive))
                uri = 'http://%s:%s/kv-meta/changed/%d' % (addr, port, self.last_alive)
                try:
                    r = rq.get(uri)
                    logger.debug("SYNC kv-changed response from %s " % repl['name'], r)
                    try:
                        to_merge = json.loads(r.text)
                    except (ValueError, TypeError), exp:
                        logger.debug('SYNC : error asking to %s: %s' % (repl['name'], str(exp)))
                        continue
                    kvmgr.do_merge(to_merge)
                    logger.debug("SYNC thread done, bailing out")
                    return
                except HTTP_EXCEPTIONS, exp:
                    logger.debug('SYNC : error asking to %s: %s' % (repl['name'], str(exp)))
                    continue
            time.sleep(1)
    
    
    # Main thread for launching generators
    def do_generator_thread(self):
        logger.log('GENERATOR thread launched')
        while not stopper.interrupted:
            logger.debug('Looking for %d generators' % len(self.generators))
            for (gname, gen) in self.generators.iteritems():
                logger.debug('LOOK AT GENERATOR', gen, 'to be apply on', gen['apply_on'], 'with our tags', gossiper.tags)
                apply_on = gen['apply_on']
                # Maybe this generator is not for us...
                if apply_on != '*' and apply_on not in gossiper.tags:
                    continue
                logger.debug('Generator %s will runs' % gname)
                g = Generator(gen)
                logger.debug('Generator %s will generate' % str(g.__dict__))
                g.generate()
                logger.debug('Generator %s is generated' % str(g.__dict__))
                should_launch = g.write_if_need()
                if should_launch:
                    g.launch_command()
            time.sleep(1)
    
    
    # Thread that will look for libexec/configuration change events,
    # will get the newest value in the KV and dump the files
    def do_update_libexec_cfg_thread(self):
        while not stopper.interrupted:
            # work on a clean list
            libexec_to_update = self.libexec_to_update
            self.libexec_to_update = []
            for (p, _hash) in libexec_to_update:
                logger.debug("LIBEXEC WE NEED TO UPDATE THE LIBEXEC PATH", p, "with the hash", _hash)
                fname = os.path.normpath(os.path.join(self.libexec_dir, p))
                
                # check if we are still in the libexec dir and not higer, somewhere
                # like in a ~/.ssh or an /etc...
                if not fname.startswith(self.libexec_dir):
                    logger.log('WARNING (SECURITY): trying to update the path %s that is not in libexec dir, bailing out' % fname)
                    continue
                # If it exists, try to look at the _hash so maybe we don't have to load it again
                if os.path.exists(fname):
                    try:
                        f = open(fname, 'rb')
                        _lhash = hashlib.sha1(f.read()).hexdigest()
                        f.close()
                    except Exception, exp:
                        logger.log('do_update_libexec_cfg_thread:: error in opening the %s file: %s' % (fname, exp))
                        _lhash = ''
                    if _lhash == _hash:
                        logger.debug('LIBEXEC update, not need for the local file %s, hash are the same' % fname)
                        continue
                # ok here we need to load the KV value (a base64 tarfile)
                v64 = kvmgr.get_key('__libexec/%s' % p)
                if v64 is None:
                    logger.log('WARNING: cannot load the libexec script from kv %s' % p)
                    continue
                vtar = base64.b64decode(v64)
                f = cStringIO.StringIO(vtar)
                with tarfile.open(fileobj=f, mode="r:gz") as tar:
                    files = tar.getmembers()
                    if len(files) != 1:
                        logger.log('WARNING: too much files in a libexec KV entry %d' % len(files))
                        continue
                    _f = files[0]
                    _fname = os.path.normpath(_f.name)
                    if not _f.isfile() or os.path.isabs(_fname):
                        logger.log(
                            'WARNING: (security) invalid libexec KV entry (not a file or absolute path) for %s' % _fname)
                        continue
                    
                    # ok the file is good, we can extract it
                    tempdir = tempfile.mkdtemp()
                    tar.extract(_f, path=tempdir)
                    
                    # now we can move all the tempdir content into the libexec dir
                    to_move = os.listdir(tempdir)
                    for e in to_move:
                        copy_dir(os.path.join(tempdir, e), self.libexec_dir)
                        logger.debug('LIBEXEC: we just upadte the %s file with a new version' % _fname)
                    # we can clean the tempdir as we don't use it anymore
                    shutil.rmtree(tempdir)
                f.close()
            
            # Now the configuration part
            configuration_to_update = self.configuration_to_update
            self.configuration_to_update = []
            for (p, _hash) in configuration_to_update:
                logger.debug("CONFIGURATION WE NEED TO UPDATE THE CONFIGURATION PATH", p, "with the hash", _hash)
                fname = os.path.normpath(os.path.join(self.configuration_dir, p))
                
                # check if we are still in the configuration dir and not higer, somewhere
                # like in a ~/.ssh or an /etc...
                if not fname.startswith(self.configuration_dir):
                    logger.log(
                        'WARNING (SECURITY): trying to update the path %s that is not in configuration dir, bailing out' % fname)
                    continue
                # If it exists, try to look at the _hash so maybe we don't have to load it again
                if os.path.exists(fname):
                    try:
                        f = open(fname, 'rb')
                        _lhash = hashlib.sha1(f.read()).hexdigest()
                        f.close()
                    except Exception, exp:
                        logger.log(
                            'do_update_configuration_cfg_thread:: error in opening the %s file: %s' % (fname, exp))
                        _lhash = ''
                    if _lhash == _hash:
                        logger.debug(
                            'CONFIGURATION update, not need for the local file %s, hash are the same' % fname)
                        continue
                # ok here we need to load the KV value (a base64 tarfile)
                v64 = kvmgr.get_key('__configuration/%s' % p)
                if v64 is None:
                    logger.log('WARNING: cannot load the configuration script from kv %s' % p)
                    continue
                vtar = base64.b64decode(v64)
                f = cStringIO.StringIO(vtar)
                with tarfile.open(fileobj=f, mode="r:gz") as tar:
                    files = tar.getmembers()
                    if len(files) != 1:
                        logger.log('WARNING: too much files in a configuration KV entry %d' % len(files))
                        continue
                    _f = files[0]
                    _fname = os.path.normpath(_f.name)
                    if not _f.isfile() or os.path.isabs(_fname):
                        logger.log(
                            'WARNING: (security) invalid configuration KV entry (not a file or absolute path) for %s' % _fname)
                        continue
                    # ok the file is good, we can extract it
                    tempdir = tempfile.mkdtemp()
                    tar.extract(_f, path=tempdir)
                    
                    # now we can move all the tempdir content into the configuration dir
                    to_move = os.listdir(tempdir)
                    for e in to_move:
                        copy_dir(os.path.join(tempdir, e), self.configuration_dir)
                        logger.debug('CONFIGURATION: we just upadte the %s file with a new version' % _fname)
                    # we can clean the tempdir as we don't use it anymore
                    shutil.rmtree(tempdir)
                f.close()
            
            # We finish to load all, we take a bit sleep now...
            time.sleep(1)
    
    
    def retention_nodes(self, force=False):
        # Ok we got no nodes? something is strange, we don't save this :)
        if len(gossiper.nodes) == 0:
            return
        
        now = int(time.time())
        if force or (now - 60 > self.last_retention_write):
            with open(self.nodes_file + '.tmp', 'w') as f:
                with gossiper.nodes_lock:
                    nodes = copy.copy(gossiper.nodes)
                f.write(jsoner.dumps(nodes))
            # now more the tmp file into the real one
            shutil.move(self.nodes_file + '.tmp', self.nodes_file)
            
            # Same for the incarnation data!
            with open(self.incarnation_file + '.tmp', 'w') as f:
                f.write(jsoner.dumps(gossiper.incarnation))
            # now more the tmp file into the real one
            shutil.move(self.incarnation_file + '.tmp', self.incarnation_file)
            
            with open(self.check_retention + '.tmp', 'w') as f:
                f.write(jsoner.dumps(monitoringmgr.checks))
            # now move the tmp into the real one
            shutil.move(self.check_retention + '.tmp', self.check_retention)
            
            with open(self.service_retention + '.tmp', 'w') as f:
                f.write(jsoner.dumps(monitoringmgr.services))
            # now move the tmp into the real one
            shutil.move(self.service_retention + '.tmp', self.service_retention)
            
            with open(self.last_alive_file + '.tmp', 'w') as f:
                f.write(jsoner.dumps(int(time.time())))
            # now move the tmp into the real one
            shutil.move(self.last_alive_file + '.tmp', self.last_alive_file)
            
            with open(self.collector_retention + '.tmp', 'w') as f:
                data = collectormgr.get_retention()
                f.write(jsoner.dumps(data))
            # now move the tmp into the real one
            shutil.move(self.collector_retention + '.tmp', self.collector_retention)
            
            self.last_retention_write = now
    
    
    def clean_lock(self):
        if os.path.exists(self.lock_path):
            logger.info('Cleaning lock file at %s' % self.lock_path)
            try:
                os.unlink(self.lock_path)
            except Exception, exp:
                logger.error('Cannot remove lock file %s: %s' % (self.lock_path, exp))
    
    
    def stack_event_broadcast(self, payload):
        msg = gossiper.create_event_msg(payload)
        b = {'send': 0, 'msg': msg}
        broadcaster.broadcasts.append(b)
        return
    
    
    # interface for manage_message, in pubsub
    def manage_message_pub(self, msg=None):
        if msg is None:
            return
        self.manage_message(msg)
    
    
    # Manage a udp message
    def manage_message(self, m):
        logger.debug('MESSAGE %s' % m)
        t = m.get('type', None)
        if t is None:  # bad message, skip it
            return
        if t == 'ack':
            logger.debug("GOT AN ACK?")
        elif t == 'alive':
            gossiper.set_alive(m)
        elif t in ['suspect', 'dead']:
            gossiper.set_suspect(m)
        elif t == 'leave':
            gossiper.set_leave(m)
        elif t == 'event':
            self.manage_event(m)
        else:
            logger.error('UNKNOWN MESSAGE', m)
    
    
    def manage_event(self, m):
        eventid = m.get('eventid', '')
        payload = m.get('payload', {})
        # if bad event or already known one, delete it
        with self.events_lock:
            if not eventid or not payload or eventid in self.events:
                return
        # ok new one, add a broadcast so we diffuse it, and manage it
        b = {'send': 0, 'msg': m}
        broadcaster.broadcasts.append(b)
        with self.events_lock:
            self.events[eventid] = m
        
        # I am the sender for this event, do not handle it
        if m.get('from', '') == self.uuid:
            return
        
        _type = payload.get('type', '')
        if not _type:
            return
        
        # If we got a libexec file update message, we append this path to the list 
        # libexec_to_update so a thread will grok the new version from KV
        if _type == 'libexec':
            path = payload.get('path', '')
            _hash = payload.get('hash', '')
            if not path or not _hash:
                return
            logger.debug('LIBEXEC UPDATE asking update for the path %s wit the hash %s' % (path, _hash))
            self.libexec_to_update.append((path, _hash))
        # Ok but for the configuration part this time
        elif _type == 'configuration':
            path = payload.get('path', '')
            _hash = payload.get('hash', '')
            if not path or not _hash:
                return
            if 'path' == 'local.json':
                # We DONT update our local.json file, it's purely local
                return
            logger.debug('CONFIGURATION UPDATE asking update for the path %s wit the hash %s' % (path, _hash))
            self.configuration_to_update.append((path, _hash))
        # Maybe we are ask to clean our configuration, if so launch a thread because we can't block this
        # thread while doing it
        elif _type == 'configuration-cleanup':
            threader.create_and_launch(self.do_configuration_cleanup, name='configuration-cleanup')
        else:
            logger.debug('UNKNOWN EVENT %s' % m)
            return
    
    
    # Look at the /kv/configuration/ entry, uncompress the json string
    # and clean old files into the configuration directory that is not in this list
    # but not the local.json that is out of global conf
    def do_configuration_cleanup(self):
        zj64 = kvmgr.get_key('__configuration')
        if zj64 is None:
            logger.log('WARNING cannot grok kv/__configuration entry')
            return
        zj = base64.b64decode(zj64)
        j = zlib.decompress(zj)
        lst = json.loads(j)
        logger.debug("WE SHOULD CLEANUP all but not", lst)
        local_files = [os.path.join(dp, f)
                       for dp, dn, filenames in os.walk(os.path.abspath(self.configuration_dir))
                       for f in filenames]
        for fname in local_files:
            path = fname[len(os.path.abspath(self.configuration_dir)) + 1:]
            # Ok, we should not have the local.json entry, but even if we got it, do NOT rm it
            if path == 'local.json':
                continue
            if path not in lst:
                full_path = os.path.join(self.configuration_dir, path)
                logger.debug("CLEANUP we should clean the file", full_path)
                try:
                    os.remove(full_path)
                except OSError, exp:
                    logger.log('WARNING: cannot cleanup the configuration file %s (%s)' % (full_path, exp))
    
    
    # We are joining the seed members and lock until we reach at least one
    def join(self):
        gossiper.join()
    
    
    # each second we look for all old events in order to clean and delete them :)
    def clean_old_events(self):
        now = int(time.time())
        to_del = []
        with self.events_lock:
            for (cid, e) in self.events.iteritems():
                ctime = e.get('ctime', 0)
                if ctime < now - self.max_event_age:
                    to_del.append(cid)
        # why sleep here? because I don't want to take the lock twice as quick is an udp thread
        # is also waiting for it, he is prioritary, not me
        time.sleep(0.01)
        with self.events_lock:
            for cid in to_del:
                try:
                    del self.events[cid]
                except IndexError:  # if already delete, we don't care
                    pass
    
    
    def do_memory_trim_thread(self):
        import ctypes
        import gc
        
        try:
            libc6 = ctypes.CDLL('libc.so.6')
        except Exception:
            libc6 = None
        
        # Ok let's start the real business: we stop the garbage collector, and we will manage it by
        # ourselve so we can trace this activity
        gc.disable()
        gen = 0
        _i = 0
        while not stopper.interrupted:
            _i += 1
            gen += 1
            gen %= 2
            before_collect = time.time()
            if _i % 10 == 0:  # every 5min, do a huge collect
                gen = 2
            # Launch object collection
            gc.collect(gen)
            logger.debug('Memory collection (%d) executed in %.2f' % (gen, time.time() - before_collect))

            # Remove over allocated memory from glibc, but beware, muslibc (alpine linux) do not have it
            if libc6 and hasattr(libc6, 'malloc_trim'):
                libc6.malloc_trim(0)
            time.sleep(30)
    
    
    # Guess what? yes, it is the main function
    def main(self):
        # be sure the check list are really updated now our litners are ok
        monitoringmgr.update_checks_kv()
        
        # We can now manage our memory by ourselves
        threader.create_and_launch(self.do_memory_trim_thread, name='Memory cleaning', essential=True, part='agent')
        
        # Launch gossip threads
        threader.create_and_launch(gossiper.ping_another_nodes, name='Ping other nodes', essential=True, part='gossip')
        threader.create_and_launch(gossiper.do_launch_gossip_loop, name='Cluster messages broadcasting', essential=True, part='gossip')
        threader.create_and_launch(gossiper.launch_full_sync_loop, name='Nodes full synchronization', essential=True, part='gossip')
        
        logger.log('Go go run!')
        i = -1
        while not stopper.interrupted:
            i += 1
            if i % 10 == 0:
                logger.debug('KNOWN NODES: %d, alive:%d, suspect:%d, dead:%d, leave:%d' % (
                    gossiper.count(), gossiper.count('alive'), gossiper.count('suspect'), gossiper.count('dead'),
                    gossiper.count('leave')))
            
            gossiper.look_at_deads()
            
            self.retention_nodes()
            
            self.clean_old_events()
            
            # Look if we lost some threads or not
            threader.check_alives()
            
            time.sleep(1)
        
        # EXIT PATH
        self.retention_nodes(force=True)
        
        # Clean lock file so daemon after us will be happy
        self.clean_lock()
        
        logger.info('Exiting')
