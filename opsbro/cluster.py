import os
import sys
import socket
import json
import threading
import time
import hashlib
import signal
import tempfile
import tarfile
import base64
import shutil
import zlib
import copy

# DO NOT FORGET:
# sysctl -w net.core.rmem_max=26214400


from .log import LoggerFactory
from .log import core_logger as raw_logger
from .util import get_server_const_uuid, guess_server_const_uuid, get_cpu_consumption, get_memory_consumption
from .threadmgr import threader
from .now import NOW
from .httpclient import get_http_exceptions, httper

# now singleton objects
from .gossip import gossiper
from .raft import get_rafter
from .configurationmanager import configmgr
from .kv import kvmgr
from .dockermanager import dockermgr
from .library import libstore
from .collectormanager import collectormgr
from .info import VERSION
from .stop import stopper
from .evaluater import evaluater
from .detectormgr import detecter
from .generatormgr import generatormgr
from .ts import tsmgr
from .jsonmgr import jsoner
from .modulemanager import modulemanager
from .executer import executer
from .monitoring import monitoringmgr
from .compliancemgr import compliancemgr
from .defaultpaths import DEFAULT_LIBEXEC_DIR, DEFAULT_LOCK_PATH, DEFAULT_DATA_DIR, DEFAULT_LOG_DIR, DEFAULT_CFG_DIR, DEFAULT_SOCK_PATH
from .hostingdrivermanager import get_hostingdrivermgr
from .topic import topiker, TOPIC_SERVICE_DISCOVERY, TOPIC_AUTOMATIC_DECTECTION, TOPIC_MONITORING, TOPIC_METROLOGY, TOPIC_CONFIGURATION_AUTOMATION, TOPIC_SYSTEM_COMPLIANCE
from .packer import packer
from .agentstates import AGENT_STATES
from .udplistener import get_udp_listener

# Global logger for this part
logger = LoggerFactory.create_logger('daemon')
logger_gossip = LoggerFactory.create_logger('gossip')

# TODO: use the AGENT_STATES averywhere
AGENT_STATE_INITIALIZING = AGENT_STATES.AGENT_STATE_INITIALIZING
AGENT_STATE_OK = AGENT_STATES.AGENT_STATE_OK
AGENT_STATE_STOPPED = AGENT_STATES.AGENT_STATE_STOPPED


class Cluster(object):
    def __init__(self, cfg_dir='', libexec_dir=''):
        self.set_exit_handler()
        
        # We need to keep a trace about in what state we are globally
        # * initializing= not all threads did loop once
        # * ok= all threads did loop
        # * stopping= stop in progress
        self.agent_state = AGENT_STATE_INITIALIZING
        
        # Launch the now-update thread
        NOW.launch()
        
        # This will be the place where we will get our configuration data
        self.cfg_data = {}
        self.cfg_dir = cfg_dir
        if not self.cfg_dir:
            self.cfg_dir = DEFAULT_CFG_DIR
        else:
            self.cfg_dir = os.path.abspath(self.cfg_dir)
        
        # Some default value that can be erased by the
        # main configuration file
        # Same for public/priv for the master fucking key
        self.master_key_priv = ''  # Paths
        self.master_key_pub = ''
        self.mfkey_priv = None  # real key objects
        self.mfkey_pub = None
        
        # By default, we are not a proxy, and with default port
        self.is_proxy = False
        self.port = 6768
        self.name = ''
        self.display_name = ''
        self.hostname = socket.gethostname()
        if not self.name:
            self.name = '%s' % self.hostname
        self.groups = []
        
        self.bootstrap = False
        self.seeds = []
        self.zone = ''
        
        # Topics
        self.service_discovery_topic_enabled = True
        self.automatic_detection_topic_enabled = True
        self.monitoring_topic_enabled = True
        self.metrology_topic_enabled = True
        self.configuration_automation_topic_enabled = True
        self.system_compliance_topic_enabled = True
        
        # The public IP can be a bit complex, as maybe the local host do not even have it in it's
        # network interface: EC2 and scaleway are example of public ip -> NAT -> private one and
        # the linux do not even know it
        hosttingdrvmgr = get_hostingdrivermgr()
        self.addr = hosttingdrvmgr.get_local_address()
        self.public_addr = hosttingdrvmgr.get_public_address()  # can be different for cloud based env
        
        self.listening_addr = '0.0.0.0'
        
        self.data_dir = os.path.abspath(os.path.join(DEFAULT_DATA_DIR))  # '/var/lib/opsbro/'
        self.log_dir = DEFAULT_LOG_DIR  # '/var/log/opsbro'
        self.lock_path = DEFAULT_LOCK_PATH  # '/var/run/opsbro.lock'
        self.libexec_dir = DEFAULT_LIBEXEC_DIR  # '/var/lib/opsbro/libexec'
        self.socket_path = DEFAULT_SOCK_PATH  # /var/lib/opsbro/opsbro.sock
        
        self.log_level = 'INFO'
        
        # now we read them, set it in our object
        parameters_from_local_configuration = configmgr.get_parameters_for_cluster_from_configuration()
        
        for (k, v) in parameters_from_local_configuration.items():
            logger.debug('Setting parameter from local configuration: %s => %s' % (k, v))
            setattr(self, k, v)
        
        # We can start with a void log dir too
        if not os.path.exists(self.log_dir):
            os.mkdir(self.log_dir)
        
        # Configure the logger with its new level if need
        raw_logger.setLevel(self.log_level)
        
        # open the log file
        raw_logger.load(self.log_dir, self.name)
        raw_logger.export_http()
        
        topiker.set_topic_state(TOPIC_SERVICE_DISCOVERY, self.service_discovery_topic_enabled)
        topiker.set_topic_state(TOPIC_AUTOMATIC_DECTECTION, self.automatic_detection_topic_enabled)
        topiker.set_topic_state(TOPIC_MONITORING, self.monitoring_topic_enabled)
        topiker.set_topic_state(TOPIC_METROLOGY, self.metrology_topic_enabled)
        topiker.set_topic_state(TOPIC_CONFIGURATION_AUTOMATION, self.configuration_automation_topic_enabled)
        topiker.set_topic_state(TOPIC_SYSTEM_COMPLIANCE, self.system_compliance_topic_enabled)
        
        # Look if our encryption key is valid or not
        encrypter = libstore.get_encrypter()
        
        # Same for master fucking key PRIVATE
        if self.master_key_priv:
            if not os.path.isabs(self.master_key_priv):
                self.master_key_priv = os.path.join(self.cfg_dir, self.master_key_priv)
            if not os.path.exists(self.master_key_priv):
                logger.error('Cannot find the master key private file at %s' % self.master_key_priv)
            else:
                RSA = encrypter.get_RSA()
                if RSA is None:
                    logger.error('You set a master private key but but cannot import python-rsa module, please install it. Exiting.')
                    sys.exit(2)
                
                with open(self.master_key_priv, 'r') as f:
                    buf = f.read()
                try:
                    self.mfkey_priv = RSA.PrivateKey.load_pkcs1(buf)
                except Exception as exp:
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
                RSA = encrypter.get_RSA()
                if RSA is None:
                    logger.error('You set a master public key but but cannot import python-crypto module, please install it. Exiting.')
                    sys.exit(2)
                # let's try to open the key so :)
                with open(self.master_key_pub, 'r') as f:
                    buf = f.read()
                try:
                    self.mfkey_pub = RSA.PublicKey.load_pkcs1(buf)
                except Exception as exp:
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
                logger.info("KEY: %s loaded from previous key file %s" % (self.uuid, self.server_key_file))
            else:
                # Ok no way to get from past, so try to guess the more stable possible, and if not ok, give me random stuff
                self.uuid = guess_server_const_uuid()
        
        # now save the key
        with open(self.server_key_file, 'w') as f:
            f.write(self.uuid)
        logger.info("KEY: %s saved to the key file %s" % (self.uuid, self.server_key_file))
        
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
                nodes = jsoner.loads(f.read())
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
                self.incarnation = jsoner.loads(f.read())
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
                self.last_alive = jsoner.loads(f.read())
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
        
        # Threader should export it's http objects
        threader.export_http()
        
        # by default do not launch timeserie listeners
        
        # Launch a thread that will reap all put key asked by the udp
        threader.create_and_launch(kvmgr.put_key_reaper, name='key reaper', essential=True, part='key-value')
        
        # Load all collectors instances
        collectormgr.load_collectors()
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
        
        # Raft need http too
        rafter = get_rafter()  # create rafter here, with gossip layer (default)
        rafter.export_http()
        
        # packer need http export too (lasy export)
        packer.export_http()
        
        # Load docker thing if possible
        dockermgr.export_http()
        
        # Our main object for gossip managment
        gossiper.init(nodes, nodes_lock, self.addr, self.port, self.name, self.display_name, self.incarnation, self.uuid, self.groups, self.seeds, self.bootstrap, self.zone, self.is_proxy)
        
        # About detecting groups and such things
        detecter.export_http()
        
        # Let the modules prepare themselve
        modulemanager.prepare()
        modulemanager.export_http()
        
        # We can now link checks/services based on what we have
        monitoringmgr.link_checks()
        monitoringmgr.link_services()
        # Export checks/services http interface
        monitoringmgr.export_http()
        
        # Export generators http interface
        generatormgr.export_http()
        
        # And the configuration
        configmgr.export_http()
        
        # Compliance too
        compliancemgr.export_http()
        
        # Be sure that the udp listener object is created
        udp_listener = get_udp_listener()
    
    
    # Load raw results of collectors, and give them to the
    # collectormgr that will know how to load them :)
    def load_collector_retention(self):
        if not os.path.exists(self.collector_retention):
            return
        
        logger.info('Collectors loading collector retention file %s' % self.collector_retention)
        with open(self.collector_retention, 'r') as f:
            loaded = jsoner.loads(f.read())
            collectormgr.load_retention(loaded)
        logger.info('Collectors loaded retention file %s' % self.collector_retention)
    
    
    # What to do when we receive a signal from the system
    def manage_signal(self, sig, frame):
        logger.info("I'm process %d and I received signal %s" % (os.getpid(), str(sig)))
        if sig == signal.SIGUSR1:  # if USR1, ask a memory dump
            logger.info('MANAGE USR1')
        elif sig == signal.SIGUSR2:  # if USR2, ask objects dump
            logger.info('MANAGE USR2')
        else:  # Ok, really ask us to die :)
            stopper.do_stop('Stop from signal %s received' % sig)
    
    
    def set_exit_handler(self):
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
    
    
    @staticmethod
    def launch_check_thread():
        threader.create_and_launch(monitoringmgr.do_check_thread, name='Checks executions', essential=True, part='monitoring')
    
    
    @staticmethod
    def launch_collector_thread():
        threader.create_and_launch(collectormgr.do_collector_thread, name='Collector scheduling', essential=True, part='collector')
    
    
    @staticmethod
    def launch_generator_thread():
        threader.create_and_launch(generatormgr.do_generator_thread, name='Generator scheduling', essential=True, part='generator')
    
    
    @staticmethod
    def launch_detector_thread():
        threader.create_and_launch(detecter.do_detector_thread, name='Detector scheduling', essential=True, part='detector')
    
    
    @staticmethod
    def launch_compliance_thread():
        threader.create_and_launch(compliancemgr.do_compliance_thread, name='System compliance', essential=True, part='compliance')
    
    
    @staticmethod
    def launch_replication_backlog_thread():
        threader.create_and_launch(kvmgr.do_replication_backlog_thread, name='Replication backlog', essential=True, part='key-value')
    
    
    def launch_replication_first_sync_thread(self):
        threader.create_and_launch(self.do_replication_first_sync_thread, name='First replication synchronization', essential=True, part='key-value')
    
    
    def launch_http_listeners(self):
        threader.create_and_launch(self.launch_tcp_listener, name='Http backend', essential=True, part='agent')
    
    
    def launch_pinghome_thread(self):
        threader.create_and_launch(self.launch_pinghome, name='Ping Home', essential=False, part='agent')
    
    
    @staticmethod
    def launch_modules_threads():
        # Launch modules threads
        modulemanager.launch()
    
    
    def launch_pinghome(self):
        is_travis = os.environ.get('TRAVIS', 'false') == 'true'
        headers = {'User-Agent': 'OpsBro / %s (travis:%s)' % (VERSION, is_travis)}
        try:
            httper.get('http://shinken.io/pingbro', headers=headers)
        except:  # not a problem
            pass
    
    
    # TODO: SPLIT into modules :)
    def launch_tcp_listener(self):
        from .httpdaemon import httpdaemon, http_export, response, request, abort, gserver
        
        @http_export('/agent/state')
        def get_agent_state():
            response.content_type = 'application/json'
            return jsoner.dumps(self.agent_state)
        
        
        @http_export('/agent/info')
        def get_info():
            response.content_type = 'application/json'
            r = {'agent_state'       : self.agent_state,
                 'logs'              : raw_logger.get_errors(), 'pid': os.getpid(), 'name': self.name, 'display_name': self.display_name,
                 'port'              : self.port, 'local_addr': self.addr, 'public_addr': self.public_addr, 'socket': self.socket_path, 'zone': gossiper.zone,
                 'uuid'              : gossiper.uuid,
                 'threads'           : threader.get_info(),
                 'version'           : VERSION, 'groups': gossiper.groups,
                 'docker'            : dockermgr.get_info(),
                 'collectors'        : collectormgr.get_info(),
                 'kv'                : kvmgr.get_info(),
                 'hosting_driver'    : get_hostingdrivermgr().get_driver_name(), 'hosting_drivers_state': get_hostingdrivermgr().get_drivers_state(),
                 'topics'            : topiker.get_topic_states(),
                 'monitoring'        : monitoringmgr.get_infos(),
                 'compliance'        : compliancemgr.get_infos(),
                 'cpu_consumption'   : get_cpu_consumption(),
                 'memory_consumption': get_memory_consumption(),
                 'generators'        : generatormgr.get_infos(),
                 }
            
            # Update the infos with modules ones
            mod_infos = modulemanager.get_infos()
            r['modules'] = mod_infos
            
            r['httpservers'] = {}
            # Look at both http servers
            for (k, server) in gserver.items():
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
            return generatormgr.generators
        
        
        @http_export('/agent/generators/:gname#.+#')
        def agent_generator(gname):
            response.content_type = 'application/json'
            logger.debug("/agent/generator is called for %s" % gname)
            if gname not in generatormgr.generators:
                return abort(404, 'generator not found')
            return generatormgr.generators[gname]
        
        
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
                gossiper.stack_event_broadcast(payload)
        
        
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
                
                # print "READ A %d file %s and compressed into a %d one..." % (len(zbuf), path, len(buf64))
                key = '__configuration/%s' % path
                # print "READ PUT KEY", key
                kvmgr.put_key(key, buf64)
                
                payload = {'type': 'configuration', 'path': path, 'hash': _hash}
                gossiper.stack_event_broadcast(payload)
            
            ok_files = [fname[len(os.path.abspath(self.configuration_dir)) + 1:] for fname in all_files]
            logger.debug("propagate configuration All files", ok_files)
            j = json.dumps(ok_files)
            zj = zlib.compress(j, 9)
            zj64 = base64.b64encode(zj)
            kvmgr.put_key('__configuration', zj64)
            payload = {'type': 'configuration-cleanup'}
            gossiper.stack_event_broadcast(payload)
        
        
        @http_export('/configuration/update', method='PUT')
        def update_configuration():
            value = request.body.getvalue()
            logger.debug("HTTP: configuration update put %s" % value)
            try:
                update = jsoner.loads(value)
            except ValueError:  # bad json...
                return abort(400, 'Bad json data')
            local_file = os.path.join(self.configuration_dir, 'local.json')
            j = {}
            with open(local_file, 'r') as f:
                buf = f.read()
                j = jsoner.loads(buf)
            j.update(update)
            # Now save it
            with open(local_file, 'w') as f:
                f.write(json.dumps(j, sort_keys=True, indent=4))
            # Load the data we can
            # self.open_cfg_file(local_file)
            # TODO: get this back?
            logger.debug('HTTP configuration update, now got %s' % j)
            return
        
        
        @http_export('/configuration', method='GET')
        def get_configuration():
            response.content_type = 'application/json'
            logger.debug("HTTP: configuration get ")
            local_file = os.path.join(self.configuration_dir, 'local.json')
            
            with open(local_file, 'r') as f:
                buf = f.read()
                j = jsoner.loads(buf)
            return j
        
        
        @http_export('/agent/zone', method='PUT', protected=True)
        def post_zone():
            response.content_type = 'application/json'
            
            nzone = request.body.getvalue()
            logger.debug("HTTP: /agent/zone put %s" % nzone)
            gossiper.change_zone(nzone)
            with open(self.zone_file, 'w') as f:
                f.write(nzone)
            return json.dumps(True)
        
        
        @http_export('/stop', protected=True)
        def do_stop():
            stopper.do_stop('stop call from the CLI/API')
            return 'OK'
        
        
        @http_export('/debug/memory', protected=True)
        def do_memory_dump():
            response.content_type = 'application/json'
            try:
                from meliae import scanner
            except ImportError:
                logger.error('Cannot run a memory dump, missing python-meliae')
                return json.dumps(None)
            p = '/tmp/memory-%s' % self.name
            scanner.dump_all_objects(p)
            return json.dumps(p)
        
        
        threader.create_and_launch(httpdaemon.run, name='External HTTP', args=(self.listening_addr, self.port, ''), essential=True, part='agent')
        # Create the internal http thread
        # on unix, use UNIXsocket
        if os.name != 'nt':
            threader.create_and_launch(httpdaemon.run, name='Internal HTTP', args=('', 0, self.socket_path,), essential=True, part='agent')
        else:  # ok windows, I look at you, really
            threader.create_and_launch(httpdaemon.run, name='Internal HTTP', args=('127.0.0.1', 6770, '',), essential=True, part='agent')
    
    
    # The first sync thread will ask to our replicats for their lately changed value
    # and we will get the key/value from it
    def do_replication_first_sync_thread(self):
        if 'kv' not in gossiper.groups:
            logger.info('SYNC no need, I am not a KV node')
            return
        logger.info('SYNC thread launched')
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
                logger.info('SYNC try to sync from %s since the time %s' % (repl['name'], self.last_alive))
                uri = 'http://%s:%s/kv-meta/changed/%d' % (addr, port, self.last_alive)
                try:
                    r = httper.get(uri)
                    logger.debug("SYNC kv-changed response from %s " % repl['name'], len(r))
                    try:
                        to_merge = jsoner.loads(r)
                    except (ValueError, TypeError) as exp:
                        logger.debug('SYNC : error asking to %s: %s' % (repl['name'], str(exp)))
                        continue
                    kvmgr.do_merge(to_merge)
                    logger.debug("SYNC thread done, bailing out")
                    return
                except get_http_exceptions() as exp:
                    logger.debug('SYNC : error asking to %s: %s' % (repl['name'], str(exp)))
                    continue
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
            except Exception as exp:
                logger.error('Cannot remove lock file %s: %s' % (self.lock_path, exp))
    
    
    # We are joining the seed members and lock until we reach at least one
    @staticmethod
    def join():
        if topiker.is_topic_enabled(TOPIC_SERVICE_DISCOVERY):
            gossiper.join()
    
    
    @staticmethod
    def do_memory_trim_thread():
        try:
            import ctypes
        except ImportError:  # like in static python
            ctypes = None
        
        if ctypes is None:  # nop
            while not stopper.is_stop():
                time.sleep(10)
            return
        
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
        while not stopper.is_stop():
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
    
    
    def update_agent_state(self):
        if self.agent_state == AGENT_STATE_INITIALIZING:
            b = True
            b &= collectormgr.did_run
            b &= detecter.did_run
            b &= generatormgr.did_run
            b &= compliancemgr.did_run
            if b:
                self.agent_state = AGENT_STATE_OK
    
    
    # In one shot mode, we want to be sure the theses parts did run at least once:
    # collector
    # detector
    # generator
    # compliance
    def wait_one_shot_end(self):
        while self.agent_state == AGENT_STATE_INITIALIZING:
            self.update_agent_state()
            time.sleep(0.1)
        
        # Ok all did launched, we can quit
        
        # Ok let's know the whole system we are going to stop
        msg = 'One shot execution did finish to look at jobs, exiting'
        stopper.do_stop(msg)
        logger.info(msg)
    
    
    def __exit_path(self):
        # Change the agent_state to stopped
        self.agent_state = AGENT_STATE_STOPPED
        
        # Maybe the modules want a special call
        modulemanager.stopping_agent()
        
        # EXIT PATH
        self.retention_nodes(force=True)
        
        # Clean lock file so daemon after us will be happy
        self.clean_lock()
        
        logger.info('Exiting')
    
    
    # Guess what? yes, it is the main function
    # One shot option is for an execution that is just doing some stuff and then exit
    # so without having to start all the listening part
    def main(self, one_shot=False):
        # gossip UDP and the whole HTTP part is useless in a oneshot execution
        if not one_shot:
            logger.info('Launching listeners')
            get_udp_listener().launch_gossip_listener(self.addr, self.listening_addr, self.port)
            self.launch_http_listeners()
            # We need to have modules if need, maybe one of them can do something when exiting
            # but in one shot we only call them at the stop, without allow them to spawn their thread
            self.launch_modules_threads()
            self.launch_pinghome_thread()
        
        # joining is for gossip part, useless in a oneshot run
        if not one_shot:
            logger.info('Joining seeds nodes')
            self.join()
        
        logger.info('Starting check, collector and generator threads')
        
        self.launch_collector_thread()
        self.launch_detector_thread()
        self.launch_generator_thread()
        
        # We don't give a fuck at the checks for a one shot currently (maybe one day, but not today)
        if not one_shot:
            self.launch_check_thread()
        
        self.launch_compliance_thread()
        
        if 'kv' in gossiper.groups and not one_shot:
            self.launch_replication_backlog_thread()
            self.launch_replication_first_sync_thread()
        
        # We don't care about docker in one-shot disco
        if not one_shot:
            dockermgr.launch()
        
        # be sure the check list are really updated now our listners are ok
        # useless when a one shot run
        if not one_shot:
            monitoringmgr.update_checks_kv()
        
        # We can now manage our memory by ourselves, but in a one shot we won't live enough to eat the whole memory
        if not one_shot:
            threader.create_and_launch(self.do_memory_trim_thread, name='Memory cleaning', essential=True, part='agent')
        
        # Launch gossip threads, but not in one_shot run
        if not one_shot:
            threader.create_and_launch(gossiper.ping_another_nodes, name='Ping other nodes', essential=True, part='gossip')
            threader.create_and_launch(gossiper.do_launch_gossip_loop, name='Cluster messages broadcasting', essential=True, part='gossip')
            threader.create_and_launch(gossiper.launch_full_sync_loop, name='Nodes full synchronization', essential=True, part='gossip')
            threader.create_and_launch(gossiper.do_history_save_loop, name='Nodes history writing', essential=True, part='gossip')
            threader.create_and_launch(get_rafter().do_raft_thread, name='Raft managment', essential=True, part='raft')
        
        if one_shot:
            self.wait_one_shot_end()
            self.__exit_path()
            return
        
        logger.info('Go go run!')
        i = -1
        while not stopper.is_stop():
            i += 1
            if i % 10 == 0:
                logger.debug('KNOWN NODES: %d, alive:%d, suspect:%d, dead:%d, leave:%d' % (
                    gossiper.count(), gossiper.count('alive'), gossiper.count('suspect'), gossiper.count('dead'),
                    gossiper.count('leave')))
            
            # Update the agent state (initializing, ok, stopped, etc)
            self.update_agent_state()
            
            gossiper.look_at_deads()
            
            self.retention_nodes()
            
            # Look if we lost some threads or not
            threader.check_alives()
            
            time.sleep(1)
        
        self.__exit_path()
