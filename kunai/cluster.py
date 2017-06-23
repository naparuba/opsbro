import os
import sys
import socket
import json
import uuid as libuuid
import imp
import threading
import time
import random
import hashlib
import signal
import traceback
import cStringIO
import requests as rq
import subprocess
import tempfile
import tarfile
import base64
import shutil
import zlib
import re
import copy
import cPickle
# for mail handler
import smtplib
import datetime

try:
    import jinja2
except ImportError:
    jinja2 = None

try:
    from Crypto.Cipher import AES
except ImportError:
    AES = None

# DO NOT FORGET:
# sysctl -w net.core.rmem_max=26214400




from kunai.log import logger
from kunai.util import copy_dir, get_public_address
from kunai.threadmgr import threader
from kunai.perfdata import PerfDatas
from kunai.now import NOW
from kunai.httpclient import HTTP_EXCEPTIONS

from kunai.generator import Generator
# now singleton objects
from kunai.gossip import gossiper
from kunai.kv import kvmgr
from kunai.broadcast import broadcaster
from kunai.httpdaemon import httpdaemon, route, response, request, abort, gserver
from kunai.pubsub import pubsub
from kunai.dockermanager import dockermgr
from kunai.encrypter import encrypter, RSA
from kunai.collectormanager import collectormgr
from kunai.version import VERSION
from kunai.stop import stopper
from kunai.evaluater import evaluater
from kunai.detectormgr import detecter
from kunai.packer import packer
from kunai.ts import tsmgr
from kunai.jsonmgr import jsoner
from kunai.modulemanager import modulemanager
from kunai.zonemanager import zonemgr
from kunai.executer import executer
from kunai.defaultpaths import DEFAULT_LIBEXEC_DIR, DEFAULT_LOCK_PATH, DEFAULT_DATA_DIR, DEFAULT_LOG_DIR


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
        
        self.checks = {}
        self.services = {}
        self.generators = {}
        self.detectors = {}
        self.handlers = {}
        
        # keep a list of the checks names that match our tags
        self.active_checks = []
        
        # graphite
        self.graphite = None
        
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
        self.tags = [s.strip() for s in tags.split(',') if s.strip()]
        
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
        self.known_types = ['check', 'service', 'handler', 'generator', 'graphite', 'zone']
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
        logger.setLevel(self.log_level)
        
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
        logger.load(self.log_dir, self.name)
        
        # Look if our encryption key is valid or not
        if self.encryption_key:
            if AES is None:
                logger.error(
                    'You set an encryption key but cannot import python-crypto module, please install it. Exiting.')
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
                    logger.error(
                        'You set a master private key but but cannot import python-rsa module, please install it. Exiting.')
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
                    logger.error(
                        'You set a master public key but but cannot import python-crypto module, please install it. Exiting.')
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
        # * If there is a hardware one, use it, whatevet the hostname is or the local
        #   file are saying
        # * If there is not, then try to look at local file, and take if :
        #     * we have the same hostname than before
        #     * if we did change the hostname then recreate one
        self.uuid = self.get_server_const_uuid()
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
                self.uuid = self.guess_server_const_uuid()
        
        # now save the key
        with open(self.server_key_file, 'w') as f:
            f.write(self.uuid)
        logger.log("KEY: %s saved to the key file %s" % (self.uuid, self.server_key_file), part='gossip')
        
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
        self.load_check_retention()
        self.load_service_retention()
        
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
        self.launch_update_libexec_cfg_thread()
        
        # by default do not launch timeserie listeners
        
        # Compile the macro pattern once
        self.macro_pat = re.compile(r'(\$ *(.*?) *\$)+')
        
        # Launch a thread that will reap all put key asked by the udp
        threader.create_and_launch(kvmgr.put_key_reaper, name='put-key-reaper', essential=True)
        
        # Load all collectors globaly
        collectormgr.load_collectors(self.cfg_data)
        # and configuration ones from local and global configuration
        self.load_packs(self.local_configuration)
        self.load_packs(self.global_configuration)
        # and their last data
        self.load_collector_retention()
        
        # Open our TimeSerie manager and open the database in data_dir/ts
        tsmgr.tsb.load(self.data_dir)
        tsmgr.tsb.export_http()
        
        # Load key into the executor
        executer.load(self.mfkey_pub, self.mfkey_priv)
        executer.export_http()
        
        # the evaluater need us to grok into our cfg_data and such things
        evaluater.load(self.cfg_data, self.services)
        evaluater.export_http()
        
        # Load docker thing if possible
        dockermgr.launch()
        
        # Our main object for gossip managment
        gossiper.init(nodes, nodes_lock, self.addr, self.port, self.name, self.display_name, self.incarnation, self.uuid, self.tags, self.seeds, self.bootstrap, self.zone, self.is_proxy)
        
        # About detecting tags and such things
        detecter.load(self)
        detecter.export_http()
        
        # Let the modules preapre themselve
        modulemanager.prepare()
        modulemanager.export_http()
        
        # get the message in a pub-sub way
        pubsub.sub('manage-message', self.manage_message_pub)
    
    
    # Try to GET (fixed) uuid, but only if a constant one is here
    # * linux: get hardware uuid from dmi
    # * aws:   get instance uuid from url (TODO)
    # * windows: TODO
    @classmethod
    def get_server_const_uuid(cls):
        # First DMI, if there is a UUID, use it
        product_uuid_p = '/sys/class/dmi/id/product_uuid'
        if os.path.exists(product_uuid_p):
            with open(product_uuid_p, 'r') as f:
                buf = f.read()
            logger.info('[SERVER-UUID] using the DMI (bios) uuid as server unique UUID: %s' % buf.lower())
            return hashlib.sha1(buf.lower()).hexdigest()
        # TODO:
        # aws
        # windows
        return ''
    
    
    # Try to guess uuid, but can be just a guess, so TRY to have a constant
    # * openvz: take the local server ID + hostname as base
    @classmethod
    def guess_server_const_uuid(cls):
        # For OpenVZ: there is an ID that is unique but for a hardware host,
        # so to avoid have 2 different host with the same id, mix this id and the hostname
        openvz_info_p = '/proc/vz/veinfo'
        if os.path.exists(openvz_info_p):
            with open(openvz_info_p, 'r') as f:
                buf = f.read()
                # File:    ID    MORE-STUFF
                openvz_id = int(buf.strip().split(' ')[0])
                servr_uniq_id = '%s-%d' % (socket.gethostname().lower(), openvz_id)
                logger.info('[SERVER-UUID] OpenVZ: using the hostname & openvz local id as server unique UUID: %s' % servr_uniq_id)
                return hashlib.sha1(servr_uniq_id).hexdigest()
        # No merly fixed stuff? ok, pure randomness
        return hashlib.sha1(libuuid.uuid1().get_hex()).hexdigest()
    
    
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
            logger.error('ERROR: the pack directory %s is missing' % pack_dir)
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
        o = {}
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
            print "FNAME", fname
            mod_time = int(os.path.getmtime(fp))
            cname = os.path.splitext(fname)[0]
            self.import_check(check, 'file:%s' % fname, cname, mod_time=mod_time)
        
        if 'service' in o:
            service = o['service']
            if not isinstance(service, dict):
                logger.log('ERROR: the service from the file %s is not a valid dict' % fp)
                sys.exit(2)
            
            mod_time = int(os.path.getmtime(fp))
            fname = fp[len(self.cfg_dir) + 1:]
            sname = os.path.splitext(fname)[0]
            self.import_service(service, 'file:%s' % fname, sname, mod_time=mod_time)
        
        # HEHEHEHE
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
        
        if 'graphite' in o:
            graphite = o['graphite']
            if not isinstance(graphite, dict):
                logger.log('ERROR: the graphite from the file %s is not a valid dict' % fp)
                sys.exit(2)
            self.graphite = graphite
            
        if 'zone' in o:
            zone = o['zone']
            if not isinstance(zone, dict):
                logger.log('ERROR: the zone from the file %s is not a valid dict' % fp)
                sys.exit(2)
            zonemgr.add(zone)
        
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
    
    
    def load_check_retention(self):
        if not os.path.exists(self.check_retention):
            return
        
        logger.log('CHECK loading check retention file %s' % self.check_retention)
        with open(self.check_retention, 'r') as f:
            loaded = json.loads(f.read())
            for (cid, c) in loaded.iteritems():
                if cid in self.checks:
                    check = self.checks[cid]
                    to_load = ['last_check', 'output', 'state', 'state_id']
                    for prop in to_load:
                        check[prop] = c[prop]
                        # logger.debug('CHECK loaded %s' % self.checks, part='checks')
    
    
    def load_service_retention(self):
        if not os.path.exists(self.service_retention):
            return
        
        logger.log('Service loading service retention file %s' % self.service_retention)
        with open(self.service_retention, 'r') as f:
            loaded = json.loads(f.read())
            for (cid, c) in loaded.iteritems():
                if cid in self.services:
                    service = self.services[cid]
                    to_load = ['state_id', 'incarnation']
                    for prop in to_load:
                        service[prop] = c[prop]
                        # logger.debug('Services loaded %s' % self.services, part='services')
    
    
    # Load and sanatize a check object in our configuration
    def import_check(self, check, fr, name, mod_time=0, service=''):
        check['from'] = fr
        check['id'] = check['name'] = name
        defaults_ = {'interval'       : '10s', 'script': '', 'ok_output': '', 'critical_if': '',
                     'critical_output': '', 'warning_if': '', 'warning_output': '', 'last_check': 0,
                     'notes'          : ''}
        for (k, v) in defaults_.iteritems():
            if k not in check:
                check[k] = v
        if service:
            check['service'] = service
        if 'apply_on' not in check:
            # we take the basename of this check directory for the apply_on
            # and if /, take *  (aka means all)
            apply_on = os.path.basename(os.path.dirname(name))
            if not apply_on:
                apply_on = '*'
            check['apply_on'] = apply_on
            print "APPLY ON", apply_on
        check['modification_time'] = mod_time
        check['state'] = 'pending'
        check['state_id'] = 3
        check['output'] = ''
        if not 'handlers' in check:
            check['handlers'] = ['default']
        self.checks[check['id']] = check
    
    
    # We have a new check from the HTTP, save it where it need to be
    def delete_check(self, cname):
        p = os.path.normpath(os.path.join(self.cfg_dir, cname + '.json'))
        if not p.startswith(self.cfg_dir):
            raise Exception("Bad file path for your script, won't be in the cfg directory tree")
        # clean on disk
        if os.path.exists(p):
            os.unlink(p)
        # Now clean in memory too
        if cname in self.checks:
            del self.checks[cname]
        self.link_checks()
    
    
    # We have a new check from the HTTP, save it where it need to be
    def save_check(self, cname, check):
        p = os.path.normpath(os.path.join(self.cfg_dir, cname + '.json'))
        if not p.startswith(self.cfg_dir):
            raise Exception("Bad file path for your script, won't be in the cfg directory tree")
        
        # Look if the file directory exists or if not cannot be created
        p_dir = os.path.dirname(p)
        if not os.path.exists(p_dir):
            os.makedirs(p_dir)
        
        # import a copy, so we don't mess with the fields we need to save
        to_import = copy.copy(check)
        # Now import it in our running part
        self.import_check(to_import, 'from:http', cname)
        # and put the new one in the active running checks, maybe
        self.link_checks()
        
        # Now we can save the received entry, but first clean unless props
        to_remove = ['from', 'last_check', 'modification_time', 'state', 'output', 'state_id', 'id']
        for prop in to_remove:
            try:
                del check[prop]
            except KeyError:
                pass
        
        o = {'check': check}
        logger.debug('HTTP check saving the object %s into the file %s' % (o, p), part='http')
        buf = json.dumps(o, sort_keys=True, indent=4)
        tempdir = tempfile.mkdtemp()
        f = open(os.path.join(tempdir, 'temp.json'), 'w')
        f.write(buf)
        f.close()
        shutil.move(os.path.join(tempdir, 'temp.json'), p)
        shutil.rmtree(tempdir)
    
    
    def import_service(self, service, fr, sname, mod_time=0):
        service['from'] = fr
        service['name'] = service['id'] = sname
        if 'notes' not in service:
            service['notes'] = ''
        if 'apply_on' not in service:
            # we take the basename of this check directory for the apply_on
            # and if /, take the service name
            apply_on = os.path.basename(os.path.dirname(sname))
            if not apply_on:
                apply_on = service['name']
            service['apply_on'] = service['name']
            print "APPLY SERVICE ON", apply_on
        apply_on = service['apply_on']
        if 'check' in service:
            check = service['check']
            cname = 'service:%s' % sname
            # for the same apply_on of the check as ourself
            check['apply_on'] = apply_on
            self.import_check(check, fr, cname, mod_time=mod_time, service=service['id'])
        
        # Put the default state to unknown, retention will load
        # the old data
        service['state_id'] = 3
        service['modification_time'] = mod_time
        service['incarnation'] = 0
        
        # Add it into the services list
        self.services[service['id']] = service
    
    
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
            logger.error('Generator %s if_partial_missing property is not valid: %s' % (generator['name'], generator['if_partial_missing']), part='generator')
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
    
    
    # We have a new service from the HTTP, save it where it need to be
    def save_service(self, sname, service):
        p = os.path.normpath(os.path.join(self.cfg_dir, sname + '.json'))
        if not p.startswith(self.cfg_dir):
            raise Exception("Bad file path for your script, won't be in the cfg directory tree")
        
        # Look if the file directory exists or if not cannot be created
        p_dir = os.path.dirname(p)
        if not os.path.exists(p_dir):
            os.makedirs(p_dir)
        
        # import a copy, so we dont mess with the fieldsweneed to save
        to_import = copy.copy(service)
        # Now import it in our running part
        self.import_service(to_import, 'from:http', sname)
        # and put the new one in the active running checks, maybe
        self.link_services()
        
        # We maybe got a new service, so export this data to every one in the gossip way :)
        gossiper.increase_incarnation_and_broadcast('alive')
        
        # Now we can save the received entry, but first clean unless props
        to_remove = ['from', 'last_check', 'modification_time', 'state', 'output', 'state_id', 'id']
        for prop in to_remove:
            try:
                del service[prop]
            except KeyError:
                pass
        
        o = {'service': service}
        logger.debug('HTTP service saving the object %s into the file %s' % (o, p), part='http')
        buf = json.dumps(o, sort_keys=True, indent=4)
        tempdir = tempfile.mkdtemp()
        f = open(os.path.join(tempdir, 'temp.json'), 'w')
        f.write(buf)
        f.close()
        shutil.move(os.path.join(tempdir, 'temp.json'), p)
        shutil.rmtree(tempdir)
    
    
    # We have a new check from the HTTP, save it where it need to be
    def delete_service(self, sname):
        p = os.path.normpath(os.path.join(self.cfg_dir, sname + '.json'))
        if not p.startswith(self.cfg_dir):
            raise Exception("Bad file path for your script, won't be in the cfg directory tree")
        # clean on disk
        if os.path.exists(p):
            os.unlink(p)
        # Now clean in memory too
        if sname in self.services:
            del self.services[sname]
        self.link_services()
        # We maybe got a less service, so export this data to every one in the gossip way :)
        gossiper.increase_incarnation_and_broadcast('alive')
    
    
    # Look at our services dict and link the one we are apply_on
    # so the other nodes are aware about our tags/service
    def link_services(self):
        logger.debug('LINK my services and my node entry')
        node = gossiper.get(self.uuid)
        tags = node['tags']
        for (sname, service) in self.services.iteritems():
            apply_on = service.get('apply_on', '')
            if apply_on and apply_on in tags:
                node['services'][sname] = service
    
    
    # For checks we will only populate our active_checks list
    # with the name of the checks we are apply_on about
    def link_checks(self):
        logger.debug('LOOKING FOR our checks that match our tags')
        node = gossiper.get(self.uuid)
        tags = node['tags']
        active_checks = []
        for (cname, check) in self.checks.iteritems():
            apply_on = check.get('apply_on', '*')
            if apply_on == '*' or apply_on in tags:
                active_checks.append(cname)
        self.active_checks = active_checks
        # Also update our checks list in KV space
        self.update_checks_kv()
        # and in our own node object
        checks_entry = {}
        for (cname, check) in self.checks.iteritems():
            if cname not in active_checks:
                continue
            checks_entry[cname] = {'state_id': check['state_id']}  # by default state are unknown
        node['checks'] = checks_entry
    
    
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
    
    
    def log(self, *args):
        logger.log(args)
    
    
    def launch_check_thread(self):
        self.check_thread = threader.create_and_launch(self.do_check_thread, name='check-thread', essential=True)
    
    
    def launch_collector_thread(self):
        self.collector_thread = threader.create_and_launch(collectormgr.do_collector_thread, name='collector-thread', essential=True)
    
    
    def launch_generator_thread(self):
        self.generator_thread = threader.create_and_launch(self.do_generator_thread, name='generator-thread', essential=True)
    
    
    def launch_detector_thread(self):
        self.detector_thread = threader.create_and_launch(detecter.do_detector_thread, name='detector-thread', essential=True)
    
    
    def launch_replication_backlog_thread(self):
        self.replication_backlog_thread = threader.create_and_launch(kvmgr.do_replication_backlog_thread, name='replication-backlog-thread', essential=True)
    
    
    def launch_replication_first_sync_thread(self):
        self.replication_first_sync_thread = threader.create_and_launch(self.do_replication_first_sync_thread, name='replication-first-sync-thread', essential=True)
    
    
    def launch_listeners(self):
        self.udp_thread = threader.create_and_launch(self.launch_udp_listener, name='udp-thread', essential=True)
        self.tcp_thread = threader.create_and_launch(self.launch_tcp_listener, name='tcp-thread', essential=True)
        
        # Launch modules threads
        modulemanager.launch()
    
    
    def launch_udp_listener(self):
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        logger.info("OPENING UDP", self.addr)
        self.udp_sock.bind((self.listening_addr, self.port))
        logger.log("UDP port open", self.port, part='udp')
        while not stopper.interrupted:
            try:
                data, addr = self.udp_sock.recvfrom(65535)  # buffer size is 1024 bytes
            except socket.timeout:
                continue  # nothing in few seconds? just loop again :)
            
            # No data? bail out :)
            if len(data) == 0:
                continue
            
            # Look if we use encryption
            data = encrypter.decrypt(data)
            # Maybe the decryption failed?
            if data == '':
                continue
            logger.debug("UDP: received message:", data, addr, part='udp')
            # Ok now we should have a json to parse :)
            try:
                raw = json.loads(data)
            except ValueError:  # garbage
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
        
        @route('/agent/state/:nuuid')
        @route('/agent/state')
        def get_state(nuuid=''):
            response.content_type = 'application/json'
            r = {'checks': {}, 'services': {}}
            # by default it's us
            # maybe its us, maybe not
            if nuuid == '' or nuuid == self.uuid:
                for (cid, check) in self.checks.iteritems():
                    # maybe this chck is not a activated one for us, if so, bail out
                    if cid not in self.active_checks:
                        continue
                    r['checks'][cid] = check
                r['services'] = gossiper.get(self.uuid)['services']
                return r
            else:  # find the elements
                node = gossiper.get(nuuid)
                if node is None:
                    return abort(404, 'This node is not found')
                # Services are easy, we already got them
                r['services'] = node['services']
                # checks are harder, we must find them in the kv nodes
                v = kvmgr.get_key('__health/%s' % node['uuid'])
                if v is None or v == '':
                    logger.error('Cannot access to the checks list for', nuuid, part='http')
                    return r
                
                lst = json.loads(v)
                for cid in lst:
                    v = kvmgr.get_key('__health/%s/%s' % (node['uuid'], cid))
                    if v is None:  # missing check entry? not a real problem
                        continue
                    check = json.loads(v)
                    r['checks'][cid] = check
                return r
        
        
        @route('/agent/info')
        def get_info():
            response.content_type = 'application/json'
            r = {'logs'      : logger.get_errors(), 'pid': os.getpid(), 'name': self.name, 'display_name': self.display_name,
                 'port'      : self.port, 'addr': self.addr, 'socket': self.socket_path, 'zone': gossiper.zone,
                 'uuid'      : self.uuid, 'graphite': self.graphite,
                 'threads'   : threader.get_info(),
                 'version'   : VERSION, 'tags': self.tags,
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
                # if available get stats
                s = server.stats
                nb_threads = s['Threads'](s)
                idle_threads = s['Threads Idle'](s)
                q = s['Queue'](s)
                r['httpservers'][k] = {'nb_threads': nb_threads, 'idle_threads': idle_threads, 'queue': q}
            
            return r
        
        
        # We want a state of all our services, with the members
        @route('/state/services')
        def state_services():
            response.content_type = 'application/json'
            logger.debug("/state/services is called", part='http')
            # We don't want to modify our services objects
            services = copy.deepcopy(self.services)
            for service in services.values():
                service['members'] = []
                service['passing-members'] = []
                service['passing'] = 0
                service['failing-members'] = []
                service['failing'] = 0
            with gossiper.nodes_lock:
                for (uuid, node) in gossiper.nodes.iteritems():
                    for (sname, service) in node['services'].iteritems():
                        if sname not in services:
                            continue
                        services[sname]['members'].append(node['name'])
                        if service['state_id'] == 0:
                            services[sname]['passing'] += 1
                            services[sname]['passing-members'].append(node['name'])
                        else:
                            services[sname]['failing'] += 1
                            services[sname]['failing-members'].append(node['name'])
            
            return services
        
        
        # We want a state of all our services, with the members
        @route('/state/services/:sname')
        def state_service(sname):
            response.content_type = 'application/json'
            logger.debug("/state/services/%s is called" % sname, part='http')
            # We don't want to modify our services objects
            services = copy.deepcopy(self.services)
            service = services.get(sname, {})
            if not service:
                return {}
            service['members'] = []
            service['passing-members'] = []
            service['passing'] = 0
            service['failing-members'] = []
            service['failing'] = 0
            sname = service.get('name')
            with gossiper.nodes_lock:
                for (uuid, node) in gossiper.nodes.iteritems():
                    if sname not in node['services']:
                        continue
                    service['members'].append(node['name'])
                    if service['state_id'] == 0:
                        service['passing'] += 1
                        service['passing-members'].append(node['name'])
                    else:
                        service['failing'] += 1
                        service['failing-members'].append(node['name'])
            
            return service
        
        
        @route('/agent/checks')
        def agent_checks():
            response.content_type = 'application/json'
            logger.debug("/agent/checks is called", part='http')
            return self.checks
        
        
        @route('/agent/checks/:cname#.+#')
        def agent_check(cname):
            response.content_type = 'application/json'
            logger.debug("/agent/checks is called for %s" % cname, part='http')
            if cname not in self.checks:
                return abort(404, 'check not found')
            return self.checks[cname]
        
        
        @route('/agent/checks/:cname#.+#', method='DELETE')
        def agent_DELETE_check(cname):
            logger.debug("/agent/checks DELETE is called for %s" % cname, part='http')
            if cname not in self.checks:
                return
            self.delete_check(cname)
            return
        
        
        @route('/agent/checks/:cname#.+#', method='PUT')
        def interface_PUT_agent_check(cname):
            value = request.body.getvalue()
            logger.debug("HTTP: PUT a new/change check %s (value:%s)" % (cname, value), part='http')
            try:
                check = json.loads(value)
            except ValueError:  # bad json
                return abort(400, 'Bad json entry')
            logger.debug("HTTP: PUT a new/change check %s (value:%s)" % (cname, check), part='http')
            self.save_check(cname, check)
            return
        
        
        @route('/agent/services')
        def agent_services():
            response.content_type = 'application/json'
            logger.debug("/agent/services is called", part='http')
            return self.services
        
        
        @route('/agent/services/:sname#.+#')
        def agent_service(sname):
            response.content_type = 'application/json'
            logger.debug("/agent/service is called for %s" % sname, part='http')
            if sname not in self.services:
                return abort(404, 'service not found')
            return self.services[sname]
        
        
        @route('/agent/services/:sname#.+#', method='PUT')
        def interface_PUT_agent_service(sname):
            value = request.body.getvalue()
            logger.debug("HTTP: PUT a new/change service %s (value:%s)" % (sname, value), part='http')
            try:
                service = json.loads(value)
            except ValueError:  # bad json
                return abort(400, 'Bad json entry')
            logger.debug("HTTP: PUT a new/change check %s (value:%s)" % (sname, service), part='http')
            self.save_service(sname, service)
            return
        
        
        @route('/agent/services/:sname#.+#', method='DELETE')
        def agent_DELETE_service(sname):
            logger.debug("/agent/service DELETE is called for %s" % sname, part='http')
            if sname not in self.services:
                return
            self.delete_service(sname)
            return
        
        
        @route('/agent/generators')
        def agent_generators():
            response.content_type = 'application/json'
            logger.debug("/agent/generators is called", part='http')
            return self.generators
        
        
        @route('/agent/generators/:gname#.+#')
        def agent_generator(gname):
            response.content_type = 'application/json'
            logger.debug("/agent/generator is called for %s" % gname, part='http')
            if gname not in self.generators:
                return abort(404, 'generator not found')
            return self.generators[gname]
        
        
        @route('/agent/propagate/libexec', method='GET')
        def propage_libexec():
            logger.debug("Call to propagate-configuraion", part='http')
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
                logger.debug("propagate saving FILE %s into the KV space" % fname, part='http')
                f = tempfile.TemporaryFile()
                
                with tarfile.open(fileobj=f, mode="w:gz") as tar:
                    tar.add(fname, arcname=path)
                f.seek(0)
                zbuf = f.read()
                f.close()
                buf64 = base64.b64encode(zbuf)
                
                logger.debug(
                    "propagate READ A %d file %s and compressed into a %d one..." % (len(zbuf), path, len(buf64)),
                    part='http')
                key = '__libexec/%s' % path
                
                kvmgr.put_key(key, buf64)
                
                payload = {'type': 'libexec', 'path': path, 'hash': _hash}
                self.stack_event_broadcast(payload)
        
        
        @route('/agent/propagate/configuration', method='GET')
        def propage_configuration():
            logger.debug("propagate conf call TO PROPAGATE CONFIGURATION", part='http')
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
                
                logger.debug("propagate conf SAVING FILE %s into the KV space" % fname, part='http')
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
            logger.debug("propagate configuration All files", ok_files, part='http')
            j = json.dumps(ok_files)
            zj = zlib.compress(j, 9)
            zj64 = base64.b64encode(zj)
            kvmgr.put_key('__configuration', zj64)
            payload = {'type': 'configuration-cleanup'}
            self.stack_event_broadcast(payload)
        
        
        @route('/configuration/update', method='PUT')
        def update_configuration():
            value = request.body.getvalue()
            logger.debug("HTTP: configuration update put %s" % (value), part='http')
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
            logger.debug('HTTP configuration update, now got %s' % j, part='http')
            return
        
        
        @route('/configuration', method='GET')
        def get_configuration():
            response.content_type = 'application/json'
            logger.debug("HTTP: configuration get ", part='http')
            local_file = os.path.join(self.configuration_dir, 'local.json')
            
            with open(local_file, 'r') as f:
                buf = f.read()
                j = json.loads(buf)
            return j
        
        
        @route('/agent/zone', method='PUT')
        def post_zone():
            response.content_type = 'application/json'
            
            nzone = request.body.getvalue()
            logger.debug("HTTP: /agent/zone put %s" % (nzone), part='http')
            gossiper.change_zone(nzone)
            with open(self.zone_file, 'w') as f:
                f.write(nzone)
            return json.dumps(True)
        
        
        @route('/metrics/find/')
        def get_graphite_metrics_find():
            response.content_type = 'application/json'
            key = request.GET.get('query', '*')
            print "LIST GET TS FOR KEY", key
            
            recursive = False
            if key.endswith('.*'):
                recursive = True
                key = key[:-2]
                print "LIST RECURSVIE FOR", key
            
            # Maybe ask all, if so recursive is On
            if key == '*':
                key = ''
                recursive = True
            
            r = []
            keys = tsmgr.list_keys(key)
            l = len(key)
            added = {}
            for k in keys:
                print "LIST KEY", k
                title = k[l:]
                # maybe we got a key that do not belong to us
                # like srv-linux10 when we ask for linux1
                # so if we don't got a . here, it's an invalid
                # dir
                print "LIST TITLE", title
                if key and not title.startswith('.'):
                    print "LIST SKIPPING KEY", key
                    continue
                
                # Ok here got sons, but maybe we are not asking for recursive ones, if so exit with
                # just the key as valid tree
                if not recursive:
                    print "NO RECURSIVE AND EARLY EXIT for KEY", key
                    return json.dumps(
                        [{"leaf": 0, "context": {}, 'text': key, 'id': key, "expandable": 1, "allowChildren": 1}])
                
                if title.startswith('.'):
                    title = title[1:]
                print "LIST TITLE CLEAN", title
                # if there is a . in it, it's a dir we need to have
                dname = title.split('.', 1)[0]
                # If the dnmae was not added, do it
                if dname not in added and title.count('.') != 0:
                    added[dname] = True
                    r.append({"leaf"         : 0, "context": {}, 'text': dname, 'id': k[:l] + dname, 'expandable': 1,
                              'allowChildren': 1})
                    print "LIST ADD DIR", dname, k[:l] + dname
                
                print "LIST DNAME KEY", dname, key, title.count('.')
                if title.count('.') == 0:
                    # not a directory, add it directly but only if the
                    # key asked was our directory                    
                    r.append({"leaf": 1, "context": {}, 'text': title, 'id': k, "expandable": 0, "allowChildren": 0})
                    print "LIST ADD FILE", title
            print "LIST FINALLY RETURN", r
            return json.dumps(r)
        
        
        # really manage the render call, with real return, call by a get and
        # a post function
        def do_render(targets, _from):
            response.content_type = 'application/json'
            print "TARGETS", targets
            if not targets:
                return abort(400, 'Invalid target')
            # Default past values, round at an hour
            now = int(time.time())
            pastraw = int(time.time()) - 86400
            past = divmod(pastraw, 3600)[0] * 3600
            
            found = False
            m = re.match(r'-(\d*)h', _from, re.M | re.I)
            if m:
                found = True
                nbhours = int(m.group(1))
                pastraw = int(time.time()) - (nbhours * 3600)
                past = divmod(pastraw, 3600)[0] * 3600
            if not found:
                m = re.match(r'-(\d*)hours', _from, re.M | re.I)
                if m:
                    found = True
                    nbhours = int(m.group(1))
                    pastraw = int(time.time()) - (nbhours * 3600)
                    past = divmod(pastraw, 3600)[0] * 3600
            if not found:  # absolute value maybe?
                m = re.match(r'(\d*)', _from, re.M | re.I)
                if m:
                    found = True
                    past = divmod(int(m.group(1)), 3600)[0] * 3600
            
            if not found:
                return abort(400, 'Invalid range')
            
            # Ok now got the good values
            res = []
            for target in targets:
                
                nuuid = gossiper.find_tag_node('ts', target)
                n = None
                if nuuid:
                    n = gossiper.get(nuuid)
                nname = ''
                if n:
                    nname = n['name']
                logger.debug('HTTP ts: target %s is managed by %s(%s)' % (target, nname, nuuid), part='ts')
                # that's me or the other is no more there?
                if nuuid == self.uuid or n is None:
                    logger.debug('HTTP ts: /render, my job to manage %s' % target, part='ts')
                    
                    # Maybe I am also the TS manager of these data? if so, get the TS backend data for this                    
                    min_e = hour_e = day_e = None
                    
                    logger.debug('HTTP RENDER founded TS %s' % tsmgr.tsb.data)
                    min_e = tsmgr.tsb.data.get('min::%s' % target, None)
                    hour_e = tsmgr.tsb.data.get('hour::%s' % target, None)
                    day_e = tsmgr.tsb.data.get('day::%s' % target, None)
                    logger.debug('HTTP TS RENDER, FOUNDED TS data %s %s %s' % (min_e, hour_e, day_e))
                    
                    # Get from the past, but start at the good hours offset
                    t = past
                    r = []
                    
                    while t < now:
                        # Maybe the time match a hour we got in memory, if so take there
                        if hour_e and hour_e['hour'] == t:
                            logger.debug('HTTP TS RENDER match memory HOUR, take this value instead', part='ts')
                            raw_values = hour_e['values'][:]  # copy instead of cherrypick, because it can move/append
                            for i in xrange(60):
                                # Get teh value and the time
                                e = raw_values[i]
                                tt = t + 60 * i
                                r.append((e, tt))
                                if e:
                                    logger.debug('GOT NOT NULL VALUE from RENDER MEMORY cache %s:%s' % (e, tt),
                                                 part='ts')
                        else:  # no memory match, got look in the KS part
                            ukey = '%s::h%d' % (target, t)
                            raw64 = kvmgr.get_key(ukey)
                            if raw64 is None:
                                for i in xrange(60):
                                    # Get the value and the time
                                    tt = t + 60 * i
                                    r.append((None, tt))
                            else:
                                raw = base64.b64decode(raw64)
                                v = cPickle.loads(raw)
                                raw_values = v['values']
                                for i in xrange(60):
                                    # Get teh value and the time
                                    e = raw_values[i]
                                    tt = t + 60 * i
                                    r.append((e, tt))
                        # Ok now the new hour :)
                        t += 3600
                    # Now build the final thing
                    res.append({"target": target, "datapoints": r})
                else:  # someone else job, rely the question
                    uri = 'http://%s:%s/render/?target=%s&from=%s' % (n['addr'], n['port'], target, _from)
                    try:
                        logger.debug('TS: (get /render) relaying to %s: %s' % (n['name'], uri), part='ts')
                        r = rq.get(uri)
                        logger.debug('TS: get /render founded (%d)' % len(r.text), part='ts')
                        v = json.loads(r.text)
                        logger.debug("TS /render relay GOT RETURN", v, "AND RES", res)
                        res.extend(v)
                        logger.debug("TS /render res is now", res)
                    except HTTP_EXCEPTIONS, exp:
                        logger.debug('TS: /render relay error asking to %s: %s' % (n['name'], str(exp)), part='ts')
                        continue
            
            logger.debug('TS RENDER FINALLY RETURN', res)
            return json.dumps(res)
        
        
        @route('/render')
        @route('/render/')
        def get_ts_values():
            targets = request.GET.getall('target')
            _from = request.GET.get('from', '-24hours')
            return do_render(targets, _from)
        
        
        @route('/render', method='POST')
        @route('/render/', method='POST')
        def get_ts_values():
            targets = request.POST.getall('target')
            _from = request.POST.get('from', '-24hours')
            return do_render(targets, _from)
        
        
        # TODO: only in the local socket http webserver
        @route('/stop')
        def do_stop():
            pubsub.pub('interrupt')
            return 'OK'
        
        
        self.external_http_thread = threader.create_and_launch(httpdaemon.run, name='external-http-thread',
                                                               args=(self.listening_addr, self.port, ''),
                                                               essential=True)
        # Create the internal http thread
        # on unix, use UNIXsocket
        if os.name != 'nt':
            self.internal_http_thread = threader.create_and_launch(httpdaemon.run, name='internal-http-thread', args=('', 0, self.socket_path,), essential=True)
        else:  # ok windows, I look at you, really
            self.internal_http_thread = threader.create_and_launch(httpdaemon.run, name='internal-http-thread', args=('127.0.0.1', 6770, '',), essential=True)
    
    
    # launch metric based listeners and backend
    def start_ts_listener(self):
        
        tsmgr.start_threads()
    
    
    # The first sync thread will ask to our replicats for their lately changed value
    # and we will get the key/value from it
    def do_replication_first_sync_thread(self):
        if 'kv' not in self.tags:
            logger.log('SYNC no need, I am not a KV node', part='kv')
            return
        logger.log('SYNC thread launched', part='kv')
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
                logger.log('SYNC try to sync from %s since the time %s' % (repl['name'], self.last_alive), part='kv')
                uri = 'http://%s:%s/kv-meta/changed/%d' % (addr, port, self.last_alive)
                try:
                    r = rq.get(uri)
                    logger.debug("SYNC kv-changed response from %s " % repl['name'], r, part='kv')
                    try:
                        to_merge = json.loads(r.text)
                    except (ValueError, TypeError), exp:
                        logger.debug('SYNC : error asking to %s: %s' % (repl['name'], str(exp)), part='kv')
                        continue
                    kvmgr.do_merge(to_merge)
                    logger.debug("SYNC thread done, bailing out", part='kv')
                    return
                except HTTP_EXCEPTIONS, exp:
                    logger.debug('SYNC : error asking to %s: %s' % (repl['name'], str(exp)), part='kv')
                    continue
            time.sleep(1)
    
    
    # Main thread for launching checks (each with its own thread)
    def do_check_thread(self):
        logger.log('CHECK thread launched', part='check')
        cur_launchs = {}
        while not stopper.interrupted:
            now = int(time.time())
            for (cid, check) in self.checks.iteritems():
                # maybe this chck is not a activated one for us, if so, bail out
                if cid not in self.active_checks:
                    continue
                # maybe a check is already running
                if cid in cur_launchs:
                    continue
                # else look at the time
                last_check = check['last_check']
                interval = int(check['interval'].split('s')[0])  # todo manage like it should
                # in the conf reading phase
                interval = random.randint(int(0.9 * interval), int(1.1 * interval))
                
                if last_check < now - interval:
                    # randomize a bit the checks
                    script = check['script']
                    logger.debug('CHECK: launching check %s:%s' % (cid, script), part='check')
                    t = threader.create_and_launch(self.launch_check, name='check-%s' % cid, args=(check,))
                    cur_launchs[cid] = t
            
            to_del = []
            for (cid, t) in cur_launchs.iteritems():
                if not t.is_alive():
                    t.join()
                    to_del.append(cid)
            for cid in to_del:
                del cur_launchs[cid]
            
            time.sleep(1)
    
    
    # Main thread for launching generators
    def do_generator_thread(self):
        logger.log('GENERATOR thread launched', part='generator')
        while not stopper.interrupted:
            logger.debug('Looking for %d generators' % len(self.generators), part='generator')
            for (gname, gen) in self.generators.iteritems():
                logger.debug('LOOK AT GENERATOR', gen, 'to be apply on', gen['apply_on'], 'with our tags', self.tags, part='generator')
                apply_on = gen['apply_on']
                # Maybe this generator is not for us...
                if apply_on != '*' and apply_on not in self.tags:
                    continue
                logger.debug('Generator %s will runs' % gname, part='generator')
                g = Generator(gen)
                logger.debug('Generator %s will generate' % str(g.__dict__), part='generator')
                g.generate()
                logger.debug('Generator %s is generated' % str(g.__dict__), part='generator')
                should_launch = g.write_if_need()
                if should_launch:
                    g.launch_command()
            time.sleep(1)
    
    
    # Try to find the params for a macro in the foloowing objets, in that order:
    # * check
    # * service
    # * main configuration
    def _found_params(self, m, check):
        parts = [m]
        # if we got a |, we got a default value somewhere
        if '|' in m:
            parts = m.split('|', 1)
        change_to = ''
        for p in parts:
            elts = [p]
            if '.' in p:
                elts = p.split('.')
            elts = [e.strip() for e in elts]
            
            # we will try to grok into our cfg_data for the k1.k2.k3 =>
            # self.cfg_data[k1][k2][k3] entry if exists
            d = None
            founded = False
            
            # We will look into the check>service>global order
            # but skip serviec if it's not related with the check
            sname = check.get('service', '')
            
            find_into = [check, self.cfg_data]
            if sname and sname in self.services:
                service = self.services.get(sname)
                find_into = [check, service, self.cfg_data]
            
            for tgt in find_into:
                (lfounded, ld) = self._found_params_inside(elts, tgt)
                if not lfounded:
                    continue
                if lfounded:
                    founded = True
                    d = ld
                    break
            if not founded:
                continue
            change_to = str(d)
            break
        return change_to
    
    
    # Try to found a elts= k1.k2.k3 => d[k1][k2][k3] entry
    # if exists
    def _found_params_inside(self, elts, d):
        founded = False
        for e in elts:
            if e not in d:
                founded = False
                break
            d = d[e]
            founded = True
        return (founded, d)
    
    
    # Launch a check sub-process as a thread
    def launch_check(self, check):
        # If critical_if available, try it
        critical_if = check.get('critical_if')
        warning_if = check.get('warning_if')
        rc = 3  # by default unknown state and output
        output = 'Check not configured'
        err = ''
        if critical_if or warning_if:
            if critical_if:
                b = evaluater.eval_expr(critical_if, check=check)
                if b:
                    output = evaluater.eval_expr(check.get('critical_output', ''))
                    rc = 2
            if not b and warning_if:
                b = evaluater.eval_expr(warning_if, check=check)
                if b:
                    output = evaluater.eval_expr(check.get('warning_output', ''))
                    rc = 1
            # if unset, we are in OK
            if rc == 3:
                rc = 0
                output = evaluater.eval_expr(check.get('ok_output', ''))
        else:
            script = check['script']
            logger.debug("CHECK start: MACRO launching %s" % script, part='check')
            # First we need to change the script with good macros (between $$)       
            it = self.macro_pat.finditer(script)
            macros = [m.groups() for m in it]
            # can be ('$ load.warning | 95$', 'load.warning | 95') for example
            for (to_repl, m) in macros:
                change_to = self._found_params(m, check)
                script = script.replace(to_repl, change_to)
            logger.debug("MACRO finally computed", script, part='check')
            
            p = subprocess.Popen(script, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True,
                                 preexec_fn=os.setsid)
            output, err = p.communicate()
            rc = p.returncode
            # not found error like (127) should be catch as unknown check
            if rc > 3:
                rc = 3
        logger.debug("CHECK RETURN %s : %s %s %s" % (check['id'], rc, output, err), part='check')
        did_change = (check['state_id'] != rc)
        check['state'] = {0: 'ok', 1: 'warning', 2: 'critical', 3: 'unknown'}.get(rc, 'unknown')
        if 0 <= rc <= 3:
            check['state_id'] = rc
        else:
            check['state_id'] = 3
        
        check['output'] = output + err
        check['last_check'] = int(time.time())
        self.analyse_check(check, did_change)
        
        # Launch the handlers, some need the data if the element did change or not
        self.launch_handlers(check, did_change)
    
    
    # get a check return and look it it did change a service state. Also save
    # the result in the __health KV
    def analyse_check(self, check, did_change):
        logger.debug('CHECK we got a check return, deal with it for %s' % check, part='check')
        
        # if did change, update the node check entry about it
        if did_change:
            gossiper.update_check_state_id(check['name'], check['state_id'])
        
        # by default warn others nodes if the check did change
        warn_about_our_change = did_change
        
        # If the check is related to a service, import the result into the service
        # and look for a service state change
        sname = check.get('service', '')
        if sname and sname in self.services:
            service = self.services.get(sname)
            logger.debug('CHECK is related to a service, deal with it! %s => %s' % (check, service), part='check')
            sstate_id = service.get('state_id')
            cstate_id = check.get('state_id')
            if cstate_id != sstate_id:
                service['state_id'] = cstate_id
                logger.log('CHECK: we got a service state change from %s to %s for %s' % (sstate_id, cstate_id, service['name']), part='check')
                warn_about_our_change = True
            else:
                logger.debug('CHECK: service %s did not change (%s)' % (service['name'], sstate_id), part='check')
        
        # If our check or service did change, warn thers nodes about it
        if warn_about_our_change:
            gossiper.increase_incarnation_and_broadcast('alive')
        
        # We finally put the result in the KV database
        self.put_check(check)
    
    
    # Save the check as a jsono object into the __health/ KV part
    def put_check(self, check):
        value = json.dumps(check)
        key = '__health/%s/%s' % (self.uuid, check['name'])
        logger.debug('CHECK SAVING %s:%s(len=%d)' % (key, value, len(value)), part='check')
        kvmgr.put_key(key, value, allow_udp=True)
        
        # Now groking metrics from check
        elts = check['output'].split('|', 1)
        
        try:
            perfdata = elts[1]
        except IndexError:
            perfdata = ''
        
        # if not perfdata, bail out
        if not perfdata:
            return
        
        datas = []
        cname = check['name'].replace('/', '.')
        now = int(time.time())
        perfdatas = PerfDatas(perfdata)
        for m in perfdatas:
            if m.name is None or m.value is None:
                continue  # skip this invalid perfdata
            
            logger.debug('GOT PERFDATAS', m, part='check')
            logger.debug('GOT PERFDATAS', m.name, part='check')
            logger.debug('GOT PERFDATAS', m.value, part='check')
            e = {'mname': '.'.join([self.name, cname, m.name]), 'timestamp': now, 'value': m.value}
            logger.debug('PUT PERFDATA', e, part='check')
            datas.append(e)
        
        self.put_graphite_datas(datas)
    
    
    def send_mail(self, handler, check):
        
        addr_from = handler.get('addr_from', 'kunai@mydomain.com')
        smtp_server = handler.get("smtp_server", "localhost")
        smtps = handler.get("smtps", False)
        contacts = handler.get('contacts', ['admin@mydomain.com'])
        subject_p = handler.get('subject_template', 'email.subject.tpl')
        text_p = handler.get('text_template', 'email.text.tpl')
        
        # go connect now                
        try:
            print "EMAIL connection to", smtp_server
            s = smtplib.SMTP(smtp_server, timeout=30)
            
            _time = datetime.datetime.fromtimestamp(int(time.time())).strftime('%Y-%m-%d %H:%M:%S')
            
            subject_f = os.path.join(self.configuration_dir, 'templates', subject_p)
            text_f = os.path.join(self.configuration_dir, 'templates', text_p)
            
            if not os.path.exists(subject_f):
                logger.error('Missing template file %s' % subject_f)
                return
            if not os.path.exists(text_f):
                logger.error('Missing template file %s' % text_f)
                return
            with open(subject_f) as f:
                subject_buf = f.read()
            with open(text_f) as f:
                text_buf = f.read()
            
            subject_tpl = jinja2.Template(subject_buf)
            subject_m = subject_tpl.render(handler=handler, check=check, _time=_time)
            text_tpl = jinja2.Template(text_buf)
            text_m = text_tpl.render(handler=handler, check=check, _time=_time)
            
            msg = '''\
From: %s
Subject: %s

%s

''' % (addr_from, subject_m, text_m)
            # % (addr_from, check['name'], check['state'], _time, check['output'])
            print "SENDING EMAIL", addr_from, contacts, msg
            r = s.sendmail(addr_from, contacts, msg)
            s.quit()
        except Exception:
            logger.error('Cannot send email: %s' % traceback.format_exc())
    
    
    def launch_handlers(self, check, did_change):
        for hname in check['handlers']:
            handler = self.handlers.get(hname, None)
            # maybe some one did atomize this handler? if so skip it :)
            if handler is None:
                continue
            
            # Look at the state and should match severities
            if check['state'] not in handler['severities']:
                continue
            
            # maybe it's a none (untyped) handler, if so skip it
            if handler['type'] == 'none':
                continue
            elif handler['type'] == 'mail':
                if did_change:
                    print "HANDLER EMAIL" * 10, did_change, handler
                    self.send_mail(handler, check)
            else:
                logger.warning('Unknown handler type %s for %s' % (handler['type'], handler['name']))
    
    
    # TODO: RE-factorize with the TS code part
    def put_graphite_datas(self, datas):
        forwards = {}
        for e in datas:
            mname, value, timestamp = e['mname'], e['value'], e['timestamp']
            hkey = hashlib.sha1(mname).hexdigest()
            ts_node_manager = gossiper.find_tag_node('ts', hkey)
            # if it's me that manage this key, I add it in my backend
            if ts_node_manager == self.uuid:
                logger.debug("I am the TS node manager")
                print "HOW ADDING", timestamp, mname, value, type(timestamp), type(mname), type(value)
                tsmgr.tsb.add_value(timestamp, mname, value)
            # not me? stack a forwarder
            else:
                logger.debug("The node manager for this Ts is ", ts_node_manager)
                l = forwards.get(ts_node_manager, [])
                # Transform into a graphite line
                line = '%s %s %s' % (mname, value, timestamp)
                l.append(line)
                forwards[ts_node_manager] = l
        
        for (uuid, lst) in forwards.iteritems():
            node = gossiper.get(uuid)
            # maybe the node disapear? bail out, we are not lucky
            if node is None:
                continue
            packets = []
            # first compute the packets
            buf = ''
            for line in lst:
                buf += line + '\n'
                if len(buf) > 1024:
                    packets.append(buf)
                    buf = ''
            if buf != '':
                packets.append(buf)
            
            # UDP
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            for packet in packets:
                # do NOT use the node['port'], it's the internal communication, not the graphite one!
                sock.sendto(packet, (node['addr'], 2003))
            sock.close()
    
    
    # Will delete all checks into the kv and update new values, but in a thread
    def update_checks_kv(self):
        def do_update_checks_kv(self):
            logger.info("CHECK UPDATING KV checks", part='kv')
            names = []
            for (cid, check) in self.checks.iteritems():
                # Only the checks that we are really managing
                if cid in self.active_checks:
                    names.append(check['name'])
                    self.put_check(check)
            all_checks = json.dumps(names)
            key = '__health/%s' % self.uuid
            kvmgr.put_key(key, all_checks)
        
        
        # Ok go launch it :)
        threader.create_and_launch(do_update_checks_kv, name='do_update_checks_kv', args=(self,), essential=True)
    
    
    # Thread that will look for libexec/configuration change events,
    # will get the newest value in the KV and dump the files
    def launch_update_libexec_cfg_thread(self):
        def do_update_libexec_cfg_thread(self):
            while not stopper.interrupted:
                # work on a clean list
                libexec_to_update = self.libexec_to_update
                self.libexec_to_update = []
                for (p, _hash) in libexec_to_update:
                    logger.debug("LIBEXEC WE NEED TO UPDATE THE LIBEXEC PATH", p, "with the hash", _hash,
                                 part='propagate')
                    fname = os.path.normpath(os.path.join(self.libexec_dir, p))
                    
                    # check if we are still in the libexec dir and not higer, somewhere
                    # like in a ~/.ssh or an /etc...
                    if not fname.startswith(self.libexec_dir):
                        logger.log(
                            'WARNING (SECURITY): trying to update the path %s that is not in libexec dir, bailing out' % fname,
                            part='propagate')
                        continue
                    # If it exists, try to look at the _hash so maybe we don't have to load it again
                    if os.path.exists(fname):
                        try:
                            f = open(fname, 'rb')
                            _lhash = hashlib.sha1(f.read()).hexdigest()
                            f.close()
                        except Exception, exp:
                            logger.log('do_update_libexec_cfg_thread:: error in opening the %s file: %s' % (fname, exp),
                                       part='propagate')
                            _lhash = ''
                        if _lhash == _hash:
                            logger.debug('LIBEXEC update, not need for the local file %s, hash are the same' % fname,
                                         part='propagate')
                            continue
                    # ok here we need to load the KV value (a base64 tarfile)
                    v64 = kvmgr.get_key('__libexec/%s' % p)
                    if v64 is None:
                        logger.log('WARNING: cannot load the libexec script from kv %s' % p, part='propagate')
                        continue
                    vtar = base64.b64decode(v64)
                    f = cStringIO.StringIO(vtar)
                    with tarfile.open(fileobj=f, mode="r:gz") as tar:
                        files = tar.getmembers()
                        if len(files) != 1:
                            logger.log('WARNING: too much files in a libexec KV entry %d' % len(files),
                                       part='propagate')
                            continue
                        _f = files[0]
                        _fname = os.path.normpath(_f.name)
                        if not _f.isfile() or os.path.isabs(_fname):
                            logger.log(
                                'WARNING: (security) invalid libexec KV entry (not a file or absolute path) for %s' % _fname,
                                part='propagate')
                            continue
                        
                        # ok the file is good, we can extract it
                        tempdir = tempfile.mkdtemp()
                        tar.extract(_f, path=tempdir)
                        
                        # now we can move all the tempdir content into the libexec dir
                        to_move = os.listdir(tempdir)
                        for e in to_move:
                            copy_dir(os.path.join(tempdir, e), self.libexec_dir)
                            logger.debug('LIBEXEC: we just upadte the %s file with a new version' % _fname,
                                         part='propagate')
                        # we can clean the tempdir as we don't use it anymore
                        shutil.rmtree(tempdir)
                    f.close()
                
                # Now the configuration part
                configuration_to_update = self.configuration_to_update
                self.configuration_to_update = []
                for (p, _hash) in configuration_to_update:
                    logger.debug("CONFIGURATION WE NEED TO UPDATE THE CONFIGURATION PATH", p, "with the hash", _hash,
                                 part='propagate')
                    fname = os.path.normpath(os.path.join(self.configuration_dir, p))
                    
                    # check if we are still in the configuration dir and not higer, somewhere
                    # like in a ~/.ssh or an /etc...
                    if not fname.startswith(self.configuration_dir):
                        logger.log(
                            'WARNING (SECURITY): trying to update the path %s that is not in configuration dir, bailing out' % fname,
                            part='propagate')
                        continue
                    # If it exists, try to look at the _hash so maybe we don't have to load it again
                    if os.path.exists(fname):
                        try:
                            f = open(fname, 'rb')
                            _lhash = hashlib.sha1(f.read()).hexdigest()
                            f.close()
                        except Exception, exp:
                            logger.log(
                                'do_update_configuration_cfg_thread:: error in opening the %s file: %s' % (fname, exp),
                                part='propagate')
                            _lhash = ''
                        if _lhash == _hash:
                            logger.debug(
                                'CONFIGURATION update, not need for the local file %s, hash are the same' % fname,
                                part='propagate')
                            continue
                    # ok here we need to load the KV value (a base64 tarfile)
                    v64 = kvmgr.get_key('__configuration/%s' % p)
                    if v64 is None:
                        logger.log('WARNING: cannot load the configuration script from kv %s' % p, part='propagate')
                        continue
                    vtar = base64.b64decode(v64)
                    f = cStringIO.StringIO(vtar)
                    with tarfile.open(fileobj=f, mode="r:gz") as tar:
                        files = tar.getmembers()
                        if len(files) != 1:
                            logger.log('WARNING: too much files in a configuration KV entry %d' % len(files),
                                       part='propagate')
                            continue
                        _f = files[0]
                        _fname = os.path.normpath(_f.name)
                        if not _f.isfile() or os.path.isabs(_fname):
                            logger.log(
                                'WARNING: (security) invalid configuration KV entry (not a file or absolute path) for %s' % _fname,
                                part='propagate')
                            continue
                        # ok the file is good, we can extract it
                        tempdir = tempfile.mkdtemp()
                        tar.extract(_f, path=tempdir)
                        
                        # now we can move all the tempdir content into the configuration dir
                        to_move = os.listdir(tempdir)
                        for e in to_move:
                            copy_dir(os.path.join(tempdir, e), self.configuration_dir)
                            logger.debug('CONFIGURATION: we just upadte the %s file with a new version' % _fname,
                                         part='propagate')
                        # we can clean the tempdir as we don't use it anymore
                        shutil.rmtree(tempdir)
                    f.close()
                
                # We finish to load all, we take a bit sleep now...
                time.sleep(1)
        
        
        # Go launch it
        threader.create_and_launch(do_update_libexec_cfg_thread, args=(self,))
    
    
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
                f.write(jsoner.dumps(self.checks))
            # now move the tmp into the real one
            shutil.move(self.check_retention + '.tmp', self.check_retention)
            
            with open(self.service_retention + '.tmp', 'w') as f:
                f.write(jsoner.dumps(self.services))
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
    
    
    # Guess what? yes, it is the main function
    def main(self):
        # be sure the check list are really updated now our litners are ok
        self.update_checks_kv()
        
        logger.log('Go go run!')
        i = -1
        while not stopper.interrupted:
            i += 1
            if i % 10 == 0:
                logger.debug('KNOWN NODES: %d, alive:%d, suspect:%d, dead:%d, leave:%d' % (
                    gossiper.count(), gossiper.count('alive'), gossiper.count('suspect'), gossiper.count('dead'),
                    gossiper.count('leave')), part='gossip')
            
            if i % 15 == 0:
                threader.create_and_launch(gossiper.launch_full_sync, name='launch-full-sync', essential=True)
            
            if i % 2 == 1:
                threader.create_and_launch(gossiper.ping_another, name='ping-another')
            
            gossiper.launch_gossip()
            
            gossiper.look_at_deads()
            
            self.retention_nodes()
            
            self.clean_old_events()
            
            # Look if we lost some threads or not
            threader.check_alives()
            
            time.sleep(1)
            
            # if i % 30 == 0:
            #    from meliae import scanner
            #    scanner.dump_all_objects( '/tmp/memory-%s' % self.name)
        
        self.retention_nodes(force=True)
        
        # Clean lock file so daemon after us will be happy
        self.clean_lock()
        
        logger.info('Exiting')
    
    
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
            logger.debug('LIBEXEC UPDATE asking update for the path %s wit the hash %s' % (path, _hash),
                         part='propagate')
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
            logger.debug('CONFIGURATION UPDATE asking update for the path %s wit the hash %s' % (path, _hash),
                         part='propagate')
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
            logger.log('WARNING cannot grok kv/__configuration entry', part='propagate')
            return
        zj = base64.b64decode(zj64)
        j = zlib.decompress(zj)
        lst = json.loads(j)
        logger.debug("WE SHOULD CLEANUP all but not", lst, part='propagate')
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
                logger.debug("CLEANUP we should clean the file", full_path, part='propagate')
                try:
                    os.remove(full_path)
                except OSError, exp:
                    logger.log('WARNING: cannot cleanup the configuration file %s (%s)' % (full_path, exp),
                               part='propagate')
    
    
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
        # is also waiting for it, it is prioritary, not me
        time.sleep(0.01)
        with self.events_lock:
            for cid in to_del:
                try:
                    del self.events[cid]
                except IndexError:  # if already delete, we don't care
                    pass
