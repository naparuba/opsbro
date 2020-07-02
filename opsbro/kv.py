import os
import time
import threading
import socket
# gor compression of updates
import gzip
import shutil

from .httpclient import get_http_exceptions, httper
from .log import LoggerFactory
from .now import NOW
from .dbwrapper import dbwrapper
from .gossip import gossiper
from .library import libstore
from .stop import stopper
from .util import get_sha1_hash, epoch_to_human_string
from .jsonmgr import jsoner
from .ttldatabase import TTLDatabase
from .udprouter import udprouter

REPLICATS = 1

_UPDATES_DB_FILE_EXTENSION = '.lst'
_UPDATES_DB_FILE_EXTENSION_COMPRESSED_SHORT = '.gz'
_UPDATES_DB_FILES_RETENTION = 86400 * 7  # Keep 7 days of updates
_UPDATES_DB_FILE_DURATION = 3600  # one file by hour
_UPDATES_DB_COMPRESSION_LEVEL = 4 # from 1 to 9 for gzip, 4 is quite fast (10ms) and file size is OK

# Global logger for this part
logger = LoggerFactory.create_logger('key-value')


class KV_PACKET_TYPES(object):
    PUT = 'kv::put'


# Main KV backend. Reply on a local leveldb database. It's up to the
# cluster to know if we should manage a key or not, if someone give us it,
# we save it :)
class KVBackend:
    def __init__(self):
        self.data_dir = ''
        self.db_dir = ''
        self.db = None
        self.ttldb = None
        
        self.update_db_time = 0
        self.update_db = None
        self._update_db_path = None
        self.lock = threading.RLock()
        
        # We have a backlog to manage our replication by threads
        self.replication_backlog = {}
        
        # Massif send KV
        self.put_key_buffer = []
        
        # Set myself as master of the raft:: udp messages
        udprouter.declare_handler('kv', self)
    
    
    # Really load data dir and so open database
    def init(self, data_dir):
        self.data_dir = data_dir
        self.db_dir = os.path.join(data_dir, 'kv')
        self.db = dbwrapper.get_db(self.db_dir)
        self.ttldb = TTLDatabase(os.path.join(data_dir, 'ttl'))
        self._updates_files_dir = self._get_updates_db_directory()
        
        # We can now export our http interface
        self.export_http()
    
    
    def get_info(self):
        r = {'stats': self.db.GetStats(), 'backend': {}}
        if self.db:
            r['backend']['name'] = self.db.name
        return r
    
    
    # We did receive a UDP packet
    def manage_message(self, message_type, message, source_addr):
        if message_type == KV_PACKET_TYPES.PUT:
            k = message['k']
            v = message['v']
            fw = message.get('fw', False)
            # For perf data we allow the udp send
            self.put_key(k, v, allow_udp=True, fw=fw)
        else:
            logger.error('We do not manage such type of udp message: %s' % message_type)
    
    
    # We will open a file with the keys writen during a minute
    # so we can easily look at previous changed
    def get_update_db(self, t):
        cmin = divmod(t, _UPDATES_DB_FILE_DURATION)[0] * _UPDATES_DB_FILE_DURATION
        if cmin == self.update_db_time and self.update_db:
            return self.update_db
        else:  # not the good time
            if self.update_db:
                logger.debug("FLUSINH PREVIOUS DB")
                t0 = time.time()
                self.update_db.flush()
                logger.debug("FLUSH TIME: %.4f" % (time.time() - t0))
                self.update_db.close()
                # Now re-read update file and compress it in a new file, then remove the uncompress one
                with open(self._update_db_path, 'rb') as f_in:
                    with gzip.open('%s%s' % (self._update_db_path, _UPDATES_DB_FILE_EXTENSION_COMPRESSED_SHORT), 'wb', compresslevel=_UPDATES_DB_COMPRESSION_LEVEL) as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.unlink(self._update_db_path)
                logger.info("Did save all KV UPDATES from %ss was done in %.3fs" % (_UPDATES_DB_FILE_DURATION, time.time() - t0))
                self.update_db = None
            db_dir = self._updates_files_dir
            self._update_db_path = os.path.join(db_dir, '%d%s' % (cmin, _UPDATES_DB_FILE_EXTENSION))
            self.update_db = open(self._update_db_path, 'a', buffering=1024)  # do not hammer the disk, but not too far
            self.update_db_time = cmin
            return self.update_db
    
    
    def _get_updates_db_directory(self):
        db_dir = os.path.join(self.data_dir, 'kv_updates')
        if not os.path.exists(db_dir):
            os.mkdir(db_dir)
        return db_dir
    
    
    # Raw get in our db for a key
    def get(self, key):
        try:
            t0 = time.time()
            v = self.db.Get(key)
            logger.debug("TIME kv get", time.time() - t0)
            return v
        except KeyError:
            logger.error('Get for a missing key: %s' % key)
            return None
    
    
    # Put a key/value in leveldb. Compute the meta
    # entry and increate the modify_index (+1) and modify_time too
    # If ttl is et (!=0) then add an entry in a TTL database
    def put(self, key, value, ttl=0):
        # manage the meta data for this entry
        # like modification index
        metakey = '__meta/%s' % key
        try:
            metavalue = jsoner.loads(self.db.Get(metakey))
        except (ValueError, KeyError):
            metavalue = {'modify_index': 0, 'modify_time': 0}
        
        metavalue['modify_index'] += 1
        mtime = NOW.now
        metavalue['modify_time'] = mtime
        
        # Update our meta values
        self._put_meta(key, metavalue)
        
        # if we got a tll, compute the dead time, and set it
        if ttl > 0:
            dead_t = NOW.now + ttl
            self.ttldb.set_ttl(key, dead_t)
        
        # also put an entry to the update_db
        with self.lock:  # protect to not have flush and close mixed in different threads
            f = self.get_update_db(mtime)
            f.write('%s\n' % key)
        
        # and in the end save the real data :)
        self.db.Put(key, value)
    
    
    # Delete both leveldb and metadata entry
    def delete(self, key):
        try:
            self.db.Delete(key)
        except KeyError:
            pass
        # also delete the meta entry
        metakey = '__meta/%s' % key
        try:
            self.db.Delete(metakey)
        except KeyError:
            pass
    
    
    # Get a json dump of a metadata entry
    def get_meta(self, key):
        metakey = '__meta/%s' % key
        v = self.get(metakey)
        if v is None:
            return v
        try:
            return jsoner.loads(v)
        except ValueError:
            return None
    
    
    # Save a metadata entry in json
    def _put_meta(self, key, meta):
        metakey = '__meta/%s' % key
        metadata = meta
        if isinstance(meta, dict):
            metadata = jsoner.dumps(meta)
        self.db.Put(metakey, metadata)
    
    
    # Look at meta entries for data that changed since t
    # TODO: if there are update db, use them
    def _changed_since(self, t):
        # Lookup all __meta keys
        _all = list(self.db.RangeIter(key_from='__meta', key_to='__n'))
        
        r = []
        for (mkey, metaraw) in _all:
            meta = jsoner.loads(metaraw)
            
            # maybe this key is too old to be interesting
            if meta['modify_time'] <= t:
                continue
            
            ukey = mkey[len('__meta') + 1:]
            try:
                v = self.db.Get(ukey)
            except KeyError:  # should never be possible
                continue
            r.append((ukey, v, meta))
        return r
    
    
    def stack_put_key(self, k, v, ttl=0, force=False):
        self.put_key_buffer.append((k, v, ttl, force))
    
    
    # put from udp should be clean quick from the thread so it can listen to udp again and
    # not lost any udp message
    def put_key_reaper(self):
        while not stopper.is_stop():
            put_key_buffer = self.put_key_buffer
            self.put_key_buffer = []
            _t = time.time()
            if len(put_key_buffer) != 0:
                logger.debug("PUT KEY BUFFER LEN", len(put_key_buffer))
            for (k, v, ttl, force) in put_key_buffer:
                kvmgr.put_key(k, v, ttl=ttl, allow_udp=True, force=force)
            if len(put_key_buffer) != 0:
                logger.debug("PUT KEY BUFFER DONE IN", time.time() - _t)
            
            # only sleep if we didn't work at all (busy moment)
            if len(put_key_buffer) == 0:
                time.sleep(0.1)
    
    
    # Try to merge distant data from others with meta entries
    # and only take the data that are the newest
    def do_merge(self, to_merge):
        for (ukey, v, meta) in to_merge:
            metakey = '__meta/%s' % ukey
            try:
                lmeta = jsoner.loads(self.db.Get(metakey))
            except KeyError:
                continue
            # If the other mod_index is higer, we import it :)
            if meta['modify_index'] > lmeta['modify_index']:
                self._put_meta(ukey, meta)
                self.db.Put(ukey, v)
            else:
                pass
    
    
    def delete_key(self, ukey):
        # we have to compute our internal key mapping. For user key it's: /data/KEY
        key = ukey
        
        hkey = get_sha1_hash(key)
        nuuid = gossiper.find_group_node('kv', hkey)
        logger.debug('KV: DELETE node that manage the key %s' % nuuid)
        # that's me :)
        if nuuid == gossiper.uuid:
            logger.debug('KV: DELETE My job to manage %s' % key)
            kvmgr.delete(key)
            return None
        else:
            n = gossiper.get(nuuid)
            # Maybe someone delete my node, it's not fair :)
            if n is None:
                return None
            uri = 'http://%s:%s/kv/%s' % (n['public_addr'], n['port'], ukey)
            try:
                logger.debug('KV: DELETE relaying to %s: %s' % (n['name'], uri))
                httper.delete(uri)
                logger.debug('KV: DELETE return')
                return None
            except get_http_exceptions() as exp:
                logger.debug('KV: DELETE error asking to %s: %s' % (n['name'], str(exp)))
                return None
    
    
    # Get a key from whatever me or another node
    def get_key(self, ukey):
        # we have to compute our internal key mapping. For user key it's: /data/KEY
        key = ukey
        hkey = get_sha1_hash(key)
        nuuid = gossiper.find_group_node('kv', hkey)
        logger.info('KV: key %s is managed by %s' % (ukey, nuuid))
        # that's me :)
        if nuuid == gossiper.uuid:
            logger.info('KV: (get) My job to find %s' % key)
            v = self.get(key)
            return v
        else:
            logger.info('KV: another node is managing %s' % ukey)
            n = gossiper.get(nuuid)
            # Maybe the node disapears, if so bailout and say we got no luck
            if n is None:
                return None
            uri = 'http://%s:%s/kv/%s' % (n['public_addr'], n['port'], ukey)
            try:
                logger.info('KV: (get) relaying to %s: %s' % (n['name'], uri))
                status_code, r = httper.get(uri, with_status_code=True)
                if status_code == 404:
                    logger.info("GET KEY %s return a 404" % ukey)
                    return None
                logger.info('KV: get founded (%d)' % len(r))
                return r
            except get_http_exceptions() as exp:
                logger.error('KV: error asking to %s: %s' % (n['name'], str(exp)))
                return None
    
    
    def put_key(self, ukey, value, force=False, meta=None, allow_udp=False, ttl=0, fw=False):
        # we have to compute our internal key mapping. For user key it's: /data/KEY
        key = ukey
        
        hkey = get_sha1_hash(key)
        
        nuuid = gossiper.find_group_node('kv', hkey)
        
        _node = gossiper.get(nuuid)
        _name = ''
        # The node can disapear with another thread
        if _node is not None:
            _name = _node['name']
        logger.debug('KV: key should be managed by %s(%s) for %s' % (_name, nuuid, ukey), 'kv')
        # that's me if it's really for me, or it's a force one, or it's already a forward one
        if nuuid == gossiper.uuid or force or fw:
            logger.debug('KV: (put) I shoukd managed the key %s (force:%s) (fw:%s)' % (key, force, fw))
            self.put(key, value, ttl=ttl)
            
            # We also replicate the meta data from the master node
            if meta:
                self._put_meta(key, meta)
            
            # If we are in a force mode, so we do not launch a repl, we are not
            # the master node
            if force:
                return None
            
            # remember to save the replication back log entry too
            meta = self.get_meta(ukey)
            bl = {'value': (ukey, value), 'repl': [], 'hkey': hkey, 'meta': meta}
            logger.debug('REPLICATION adding backlog entry %s' % bl)
            self.replication_backlog[ukey] = bl
            return None
        else:
            n = gossiper.get(nuuid)
            if n is None:  # oups, someone is playing iwth my nodes and delete it...
                return None
            # Maybe the user did allow weak consistency, so we can use udp (like metrics)
            if allow_udp:
                try:
                    payload = {'type': KV_PACKET_TYPES.PUT, 'k': ukey, 'v': value, 'ttl': ttl, 'fw': True}
                    packet = jsoner.dumps(payload)
                    encrypter = libstore.get_encrypter()
                    enc_packet = encrypter.encrypt(packet)
                    logger.debug('KV: PUT(udp) asking %s: %s:%s' % (n['name'], n['public_addr'], n['port']))
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.sendto(enc_packet, (n['public_addr'], n['port']))
                    sock.close()
                    return None
                except Exception as exp:
                    logger.debug('KV: PUT (udp) error asking to %s: %s' % (n['name'], str(exp)))
                    return None
            # ok no allow udp here, so we switch to a classic HTTP mode :)
            uri = 'http://%s:%s/kv/%s' % (n['public_addr'], n['port'], ukey)
            try:
                logger.debug('KV: PUT asking %s: %s' % (n['name'], uri))
                params = {'ttl': ttl}
                httper.put(uri, data=value, params=params)
                logger.debug('KV: PUT return')
                return None
            except get_http_exceptions() as exp:
                logger.debug('KV: PUT error asking to %s: %s' % (n['name'], str(exp)))
                return None
    
    
    # I try to get the nodes before myself in the nodes list
    def get_my_replicats(self):
        kv_nodes = gossiper.find_group_nodes('kv')
        kv_nodes.sort()
        
        # Maybe soneone ask us a put but we are not totally joined
        # if so do not replicate this
        if gossiper.uuid not in kv_nodes:
            logger.log('WARNING: too early put, myself %s is not a kv nodes currently' % self.uuid)
            return []
        
        # You can't have more replicats that you got of kv nodes
        nb_rep = min(REPLICATS, len(kv_nodes))
        
        idx = kv_nodes.index(gossiper.uuid)
        replicats = []
        for i in range(idx - nb_rep, idx):
            nuuid = kv_nodes[i]
            # we can't be a replicat of ourselve
            if nuuid == gossiper.uuid:
                continue
            replicats.append(nuuid)
        rnames = []
        for uuid in replicats:
            # Maybe someone delete the nodes just here, so we must care about it
            n = gossiper.get(uuid)
            if n:
                rnames.append(n['name'])
        
        logger.debug('REPLICATS: myself %s replicats are %s' % (gossiper.name, rnames))
        return replicats
    
    
    def do_replication_backlog_thread(self):
        logger.log('REPLICATION thread launched')
        while not stopper.is_stop():
            # Standard switch
            replication_backlog = self.replication_backlog
            self.replication_backlog = {}
            
            replicats = self.get_my_replicats()
            if len(replicats) == 0:
                time.sleep(1)
            for (ukey, bl) in replication_backlog.items():
                # REF: bl = {'value':(ukey, value), 'repl':[], 'hkey':hkey, 'meta':meta}
                _, value = bl['value']
                for uuid in replicats:
                    _node = gossiper.get(uuid)
                    # Someone just delete my node, not fair :)
                    if _node is None:
                        continue
                    logger.debug('REPLICATION thread manage entry to %s(%s) : %s' % (_node['name'], uuid, bl))
                    
                    # Now send it :)
                    n = _node
                    uri = 'http://%s:%s/kv/%s' % (n['public_addr'], n['port'], ukey)
                    try:
                        logger.debug('KV: PUT(force) asking %s: %s' % (n['name'], uri))
                        params = {'force': True, 'meta': jsoner.dumps(bl['meta'])}
                        r = httper.put(uri, data=value, params=params)
                        logger.debug('KV: PUT(force) return %s' % r)
                    except get_http_exceptions() as exp:
                        logger.debug('KV: PUT(force) error asking to %s: %s' % (n['name'], str(exp)))
            time.sleep(1)
    
    
    def do_kv_updates_cleaning_thread(self):
        logger.log('KV Updates files cleaning threads')
        while not stopper.is_stop():
            self._clean_old_updates_files()
            time.sleep(3600)  # clean one an hour, it's not a problem
    
    
    # Look at old update database entries
    def _clean_old_updates_files(self):
        logger.info("Clean old databases updates entry")
        update_files_limit = NOW.now - _UPDATES_DB_FILES_RETENTION
        
        # Look at the databses directory that have the hour time set
        subfiles = os.listdir(self._updates_files_dir)
        
        nb_file_cleaned = 0
        for subfile in subfiles:
            # File can be raw (unfinish) or compressed
            subfile_minute = subfile.replace(_UPDATES_DB_FILE_EXTENSION_COMPRESSED_SHORT, '').replace(_UPDATES_DB_FILE_EXTENSION, '')
            try:
                file_minute = int(subfile_minute)
            except ValueError:  # who add a dir that is not a int here...
                continue
            # Is the hour available for cleaning?
            if file_minute < update_files_limit:
                try:
                    os.unlink(os.path.join(self._updates_files_dir, subfile))
                    nb_file_cleaned += 1
                except Exception as exp:
                    logger.error('Cannot remove update file %s : %s' % (subfile, exp))
        if nb_file_cleaned != 0:
            logger.info("We did cleaned %d updates files older than %s" % (nb_file_cleaned, epoch_to_human_string(update_files_limit)))
    
    
    # main method to export http interface. Must be in a method that got
    # a self entry
    def export_http(self):
        from .httpdaemon import response, http_export, abort, request
        
        @http_export('/kv/')
        @http_export('/kv')
        def list_keys():
            response.content_type = 'application/json'
            l = list(self.db.RangeIter(include_value=False))
            return jsoner.dumps(l)
        
        
        @http_export('/kv-meta/changed/:t', method='GET')
        def get_changed_since(t):
            response.content_type = 'application/json'
            t = int(t)
            return jsoner.dumps(self._changed_since(t))
        
        
        @http_export('/kv/:ukey#.+#', method='GET')
        def interface_GET_key(ukey):
            t0 = time.time()
            logger.debug("GET KEY %s" % ukey)
            v = self.get_key(ukey)
            if v is None:
                logger.debug("GET KEY %s return a 404" % ukey)
                abort(404, '')
            logger.debug("GET: get time %s" % (time.time() - t0))
            return v
        
        
        @http_export('/kv/:ukey#.+#', method='DELETE')
        def interface_DELETE_key(ukey):
            logger.debug("KV: DELETE KEY %s" % ukey)
            self.delete_key(ukey)
        
        
        @http_export('/kv/:ukey#.+#', method='PUT')
        def interface_PUT_key(ukey):
            value = request.body.getvalue()
            logger.debug("KV: PUT KEY %s (len:%d)" % (ukey, len(value)))
            force = request.GET.get('force', 'False') == 'True'
            meta = request.GET.get('meta', None)
            if meta:
                meta = jsoner.loads(meta)
            ttl = int(request.GET.get('ttl', '0'))
            self.put_key(ukey, value, force=force, meta=meta, ttl=ttl)
            return


kvmgr = KVBackend()
