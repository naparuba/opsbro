import os
import socket
import time
import hashlib
import tempfile
import tarfile
import base64
import shutil
import zlib

from .log import LoggerFactory
from .topic import topiker, TOPIC_SERVICE_DISCOVERY
from .stop import stopper
from .library import libstore
from .jsonmgr import jsoner
from .gossip import gossiper
from .kv import kvmgr
from .broadcast import broadcaster
from .pubsub import pubsub
from .util import copy_dir
from .udprouter import udprouter

logger = LoggerFactory.create_logger('daemon')
logger_gossip = LoggerFactory.create_logger('gossip')


class UDPListener(object):
    def __init__(self):
        self.libexec_to_update = []
        self.configuration_to_update = []
        
        # register myself as global message receiver
        pubsub.sub('manage-message', self.manage_message_pub)
    
    
    def launch_gossip_listener(self, addr, listening_addr, port):
        from .threadmgr import threader
        threader.create_and_launch(self.launch_udp_listener, name='UDP listener', essential=True, part='gossip', args=(addr, listening_addr, port))
        
        # We will receive a list of path to update for libexec, and we will manage them
        # in a thread so the upd thread is not blocking
        threader.create_and_launch(self.do_update_libexec_cfg_thread, name='Checks directory (libexec) updates', essential=True, part='agent')
    
    
    # interface for manage_message, in pubsub
    def manage_message_pub(self, msg=None):
        if msg is None:
            return
        self.manage_message(msg, source_addr=None)
    
    
    def manage_event(self, m):
        eventid = m.get('eventid', '')
        payload = m.get('payload', {})
        # if bad event or already known one, delete it
        with gossiper.events_lock:
            if not eventid or not payload or eventid in gossiper.events:
                return
        
        # ok new one, add a broadcast so we diffuse it, and manage it
        b = {'send': 0, 'msg': m}
        broadcaster.append(b)
        
        # Remember this event to not spam it
        gossiper.add_event(m)
        
        # I am the sender for this event, do not handle it
        if m.get('from', '') == gossiper.uuid:
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
            from .threadmgr import threader
            threader.create_and_launch(self.do_configuration_cleanup, name='configuration-cleanup')
        else:
            logger.info('Generic event received %s' % m)
            return
    
    
    # Look at the /kv/configuration/ entry, uncompress the json string
    # and clean old files into the configuration directory that is not in this list
    # but not the local.json that is out of global conf
    def do_configuration_cleanup(self):
        zj64 = kvmgr.get_key('__configuration')
        if zj64 is None:
            logger.info('WARNING cannot grok kv/__configuration entry')
            return
        zj = base64.b64decode(zj64)
        j = zlib.decompress(zj)
        lst = jsoner.loads(j)
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
                except OSError as exp:
                    logger.info('WARNING: cannot cleanup the configuration file %s (%s)' % (full_path, exp))
    
    
    def launch_udp_listener(self, addr, listening_addr, port):
        # If we do not have the right, do not listen for UDP messages
        while not topiker.is_topic_enabled(TOPIC_SERVICE_DISCOVERY):
            time.sleep(1)
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)  # Allow Broadcast (useful for node discovery)
        logger.info("OPENING UDP", addr)
        udp_sock.bind((listening_addr, port))
        logger.info("UDP port open", port)
        while not stopper.is_stop():
            try:
                data, addr = udp_sock.recvfrom(65535)  # buffer size is 1024 bytes
            except socket.timeout:
                continue  # nothing in few seconds? just loop again :)
            
            # No data? bail out :)
            if len(data) == 0:
                logger_gossip.debug("UDP: received void message from ", addr)
                continue
            
            # Look if we use encryption
            encrypter = libstore.get_encrypter()
            data = encrypter.decrypt(data)
            
            logger_gossip.info('Try to load package with zone %s' % gossiper.zone)
            
            # Maybe the decryption failed?
            if data is None:
                logger_gossip.error("UDP: received message with bad encryption key from %s" % str(addr))
                continue
            logger_gossip.info("UDP: received message:", data, 'from', addr)
            # Ok now we should have a json to parse :)
            try:
                raw = jsoner.loads(data)
            except ValueError:  # garbage
                logger_gossip.error("UDP: received message that is not valid json:", data, 'from', addr)
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
                
                # TODO: remove this
                # if t == '/ts/new':
                #     key = m.get('key', '')
                #     # Skip this message for classic nodes
                #     if key == '':
                #         continue
                #     # if TS do not have it, it will propagate it
                #     tsmgr.set_name_if_unset(key)
                if t == 'event':
                    self.manage_event(m)
                else:
                    udprouter.route_message(m, addr)
    
    
    # Thread that will look for libexec/configuration change events,
    # will get the newest value in the KV and dump the files
    def do_update_libexec_cfg_thread(self):
        while not stopper.is_stop():
            # work on a clean list
            libexec_to_update = self.libexec_to_update
            self.libexec_to_update = []
            for (p, _hash) in libexec_to_update:
                logger.debug("LIBEXEC WE NEED TO UPDATE THE LIBEXEC PATH", p, "with the hash", _hash)
                fname = os.path.normpath(os.path.join(self.libexec_dir, p))
                
                # check if we are still in the libexec dir and not higer, somewhere
                # like in a ~/.ssh or an /etc...
                if not fname.startswith(self.libexec_dir):
                    logger.info('WARNING (SECURITY): trying to update the path %s that is not in libexec dir, bailing out' % fname)
                    continue
                # If it exists, try to look at the _hash so maybe we don't have to load it again
                if os.path.exists(fname):
                    try:
                        f = open(fname, 'rb')
                        _lhash = hashlib.sha1(f.read()).hexdigest()
                        f.close()
                    except Exception as exp:
                        logger.info('do_update_libexec_cfg_thread:: error in opening the %s file: %s' % (fname, exp))
                        _lhash = ''
                    if _lhash == _hash:
                        logger.debug('LIBEXEC update, not need for the local file %s, hash are the same' % fname)
                        continue
                # ok here we need to load the KV value (a base64 tarfile)
                v64 = kvmgr.get_key('__libexec/%s' % p)
                if v64 is None:
                    logger.info('WARNING: cannot load the libexec script from kv %s' % p)
                    continue
                vtar = base64.b64decode(v64)
                StringIO = libstore.get_StringIO()
                f = StringIO(vtar)
                with tarfile.open(fileobj=f, mode="r:gz") as tar:
                    files = tar.getmembers()
                    if len(files) != 1:
                        logger.info('WARNING: too much files in a libexec KV entry %d' % len(files))
                        continue
                    _f = files[0]
                    _fname = os.path.normpath(_f.name)
                    if not _f.isfile() or os.path.isabs(_fname):
                        logger.info(
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
                    logger.info(
                        'WARNING (SECURITY): trying to update the path %s that is not in configuration dir, bailing out' % fname)
                    continue
                # If it exists, try to look at the _hash so maybe we don't have to load it again
                if os.path.exists(fname):
                    try:
                        f = open(fname, 'rb')
                        _lhash = hashlib.sha1(f.read()).hexdigest()
                        f.close()
                    except Exception as exp:
                        logger.info(
                            'do_update_configuration_cfg_thread:: error in opening the %s file: %s' % (fname, exp))
                        _lhash = ''
                    if _lhash == _hash:
                        logger.debug(
                            'CONFIGURATION update, not need for the local file %s, hash are the same' % fname)
                        continue
                # ok here we need to load the KV value (a base64 tarfile)
                v64 = kvmgr.get_key('__configuration/%s' % p)
                if v64 is None:
                    logger.info('WARNING: cannot load the configuration script from kv %s' % p)
                    continue
                vtar = base64.b64decode(v64)
                StringIO = libstore.get_StringIO()
                f = StringIO(vtar)
                with tarfile.open(fileobj=f, mode="r:gz") as tar:
                    files = tar.getmembers()
                    if len(files) != 1:
                        logger.info('WARNING: too much files in a configuration KV entry %d' % len(files))
                        continue
                    _f = files[0]
                    _fname = os.path.normpath(_f.name)
                    if not _f.isfile() or os.path.isabs(_fname):
                        logger.info(
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


_udp_listener = None


def get_udp_listener():
    global _udp_listener
    if _udp_listener is not None:
        return _udp_listener
    _udp_listener = UDPListener()
