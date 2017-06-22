import os
import json
import time
import threading
import shutil
import hashlib
import requests as rq

from kunai.httpclient import HTTP_EXCEPTIONS
from kunai.stats import STATS
from kunai.log import logger
from kunai.threadmgr import threader
from kunai.now import NOW
from kunai.dbwrapper import dbwrapper
from kunai.httpdaemon import response, route, abort
from kunai.gossip import gossiper


# This class manage the ttl entries for each key with a ttl. Each is with a 1hour precision idx key that we saved
# in the master db
# but with keeping a database by hour about the key for the housekeeping
class TTLDatabase(object):
    def __init__(self, ttldb_dir):
        self.lock = threading.RLock()
        self.dbs = {}
        self.db_cache_size = 100
        self.ttldb_dir = ttldb_dir
        if not os.path.exists(self.ttldb_dir):
            os.mkdir(self.ttldb_dir)
        # Launch a thread that will look once a minute the old entries
        threader.create_and_launch(self.ttl_cleaning_thread, name='ttl-cleaning-thread', essential=True)
    
    
    # Load the hour ttl/H base where we will save all master
    # key for the H hour
    def get_ttl_db(self, h):
        cdb = self.dbs.get(h, None)
        # If missing, look to load it but with a lock to be sure we load it only once
        if cdb is None:
            STATS.incr('ttl-db-cache-miss', 1)
            with self.lock:
                # Maybe during the lock get one other thread succedd in getting the cdb
                if not h in self.dbs:
                    # Ok really load it, but no more than self.db_cache_size
                    # databases (number of open files can increase quickly)
                    if len(self.dbs) > self.db_cache_size:
                        ttodrop = self.dbs.keys()[0]
                        del self.dbs[ttodrop]
                    _t = time.time()
                    cdb = dbwrapper.get_db(os.path.join(self.ttldb_dir, '%d' % h))  # leveldb.LevelDB(os.path.join(self.ttldb_dir, '%d' % h))
                    STATS.incr('ttl-db-open', time.time() - _t)
                    self.dbs[h] = cdb
                # Ok a malicious thread just go before us, good :)
                else:
                    cdb = self.dbs[h]
        # We alrady got it, thanks cache
        else:
            STATS.incr('ttl-db-cache-hit', 1)
        return cdb
    
    
    # Save a key in the good idx minute database
    def set_ttl(self, key, ttl_t):
        # keep keys saved by hour in the future
        ttl_t = divmod(ttl_t, 3600)[0] * 3600
        
        cdb = self.get_ttl_db(ttl_t)
        logger.debug("TTL save", key, "with ttl", ttl_t, "in", cdb, part='kv')
        cdb.Put(key, '')
    
    
    # We already droped all entry in a db, so drop it from our cache
    def drop_db(self, h):
        # now demove the database
        with self.lock:
            try:
                del self.dbs[h]
            except IndexError:  # if not there, not a problem...
                pass
        
        # And remove the files of this database
        p = os.path.join(self.ttldb_dir, '%d' % h)
        logger.log("Deleting ttl database tree", p, part='kv')
        shutil.rmtree(p, ignore_errors=True)
    
    
    # Look at the available dbs and clean all olds dbs that time are lower
    # than current hour
    def clean_old(self):
        logger.debug("TTL clean old", part='kv')
        now = NOW.now + 3600
        h = divmod(now, 3600)[0] * 3600
        # Look at the databses directory that have the hour time set
        subdirs = os.listdir(self.ttldb_dir)
        
        for d in subdirs:
            try:
                bhour = int(d)
            except ValueError:  # who add a dir that is not a int here...
                continue
            # Is the hour available for cleaning?
            if bhour < h:
                logger.log("TTL bhour is too low!", bhour, part='kv')
                # take the database and dump all keys in it
                cdb = self.get_ttl_db(bhour)
                to_del = cdb.RangeIter()
                # Now ask the cluster to delete the key, whatever it is
                for (k, v) in to_del:
                    kvmgr.delete(k)
                
                # now we clean all old entries, remove the idx database
                self.drop_db(bhour)
    
    
    # Thread that will manage the delete of the ttld-die key
    def ttl_cleaning_thread(self):
        while True:
            time.sleep(5)
            self.clean_old()


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
        self.lock = threading.RLock()
    
    
    # Really load data dir and so open database
    def init(self, data_dir):
        self.data_dir = data_dir
        self.db_dir = os.path.join(data_dir, 'kv')
        self.db = dbwrapper.get_db(self.db_dir)  # leveldb.LevelDB(self.db_dir)
        self.ttldb = TTLDatabase(os.path.join(data_dir, 'ttl'))
        
        # We can now export our http interface
        self.export_http()
    
    
    # We will open a file with the keys writen during a minute
    # so we can easily look at previous changed
    def get_update_db(self, t):
        cmin = divmod(t, 60)[0] * 60
        if cmin == self.update_db_time and self.update_db:
            # print "UPDATE DB CACHE HIT"
            return self.update_db
        else:  # not the good time
            with self.lock:  # protect to not have flush and close mixed in different threads
                # print "UPDATE DB CACHE MISS"
                if self.update_db:
                    logger.debug("FLUSINH PREVIOUS DB", part='kv')
                    t0 = time.time()
                    self.update_db.flush()
                    logger.debug("FLUSH TIME: %.4f" % (time.time() - t0), part='kv')
                    self.update_db.close()
                    self.update_db = None
            db_dir = os.path.join(self.data_dir, 'updates')
            db_path = os.path.join(db_dir, '%d.lst' % cmin)
            if not os.path.exists(db_dir):
                os.mkdir(db_dir)
            self.update_db = open(db_path, 'a')
            self.update_db_time = cmin
            return self.update_db
    
    
    # Raw get in our db for a key
    def get(self, key):
        try:
            t0 = time.time()
            v = self.db.Get(key)
            logger.debug("TIME kv get", time.time() - t0, part='kv')
            return v
        except KeyError:
            logger.error('Get for a missing key: %s' % key, part='kv')
            return None
    
    
    # Put a key/value in leveldb. Compute the meta
    # entry and increate the modify_index (+1) and modify_time too
    # If ttl is et (!=0) then add an entry in a TTL database
    def put(self, key, value, ttl=0):
        # manage the meta data for this entry
        # like modification index
        metakey = '__meta/%s' % key
        try:
            metavalue = json.loads(self.db.Get(metakey))
        except (ValueError, KeyError):
            metavalue = {'modify_index': 0, 'modify_time': 0}
        
        metavalue['modify_index'] += 1
        mtime = NOW.now
        metavalue['modify_time'] = mtime
        
        # Update our meta values
        self.put_meta(key, metavalue)
        
        # if we got a tll, compute the dead time, and set it
        if ttl > 0:
            dead_t = NOW.now + ttl
            self.ttldb.set_ttl(key, dead_t)
        
        # also put an entry to the update_db
        f = self.get_update_db(mtime)
        t0 = time.time()
        f.write('%s\n' % key)
        # print "write", time.time() - t0
        
        t0 = time.time()
        # and in the end save the real data :)
        self.db.Put(key, value)
        # print "write db", time.time() - t0
    
    
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
            return json.loads(v)
        except ValueError:
            return None
    
    
    # Save a metadata entry in json
    def put_meta(self, key, meta):
        metakey = '__meta/%s' % key
        metadata = meta
        if isinstance(meta, dict):
            metadata = json.dumps(meta)
        self.db.Put(metakey, metadata)
    
    
    # Look at meta entries for data that changed since t
    def changed_since(self, t):
        # Lookup all __meta keys
        _all = list(self.db.RangeIter(key_from='__meta', key_to='__n'))
        
        r = []
        for (mkey, metaraw) in _all:
            meta = json.loads(metaraw)
            
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
    
    
    # Try to merge distant data from others with meta entries
    # and only take the data that are the newest
    def do_merge(self, to_merge):
        for (ukey, v, meta) in to_merge:
            metakey = '__meta/%s' % ukey
            try:
                lmeta = json.loads(self.db.Get(metakey))
            except KeyError:
                continue
            # If the other mod_index is higer, we import it :)
            if meta['modify_index'] > lmeta['modify_index']:
                self.put_meta(ukey, meta)
                self.db.Put(ukey, v)
            else:
                pass
    
    
    def delete_key(self, ukey):
        # we have to compute our internal key mapping. For user key it's: /data/KEY
        key = ukey
        
        hkey = hashlib.sha1(key).hexdigest()
        nuuid = gossiper.find_tag_node('kv', hkey)
        logger.debug('KV: DELETE node that manage the key %s' % nuuid, part='kv')
        # that's me :)
        if nuuid == gossiper.uuid:
            logger.debug('KV: DELETE My job to manage %s' % key, part='kv')
            kvmgr.delete(key)
            return None
        else:
            n = gossiper.get(nuuid)
            # Maybe someone delete my node, it's not fair :)
            if n is None:
                return None
            uri = 'http://%s:%s/kv/%s' % (n['addr'], n['port'], ukey)
            try:
                logger.debug('KV: DELETE relaying to %s: %s' % (n['name'], uri), part='kv')
                r = rq.delete(uri)
                logger.debug('KV: DELETE return %s' % r.status_code, part='kv')
                return None
            except HTTP_EXCEPTIONS, exp:
                logger.debug('KV: DELETE error asking to %s: %s' % (n['name'], str(exp)), part='kv')
                return None


    # Get a key from whatever me or another node
    def get_key(self, ukey):
        # we have to compute our internal key mapping. For user key it's: /data/KEY
        key = ukey
        hkey = hashlib.sha1(key).hexdigest()
        nuuid = gossiper.find_tag_node('kv', hkey)
        logger.info('KV: key %s is managed by %s' % (ukey, nuuid), part='kv')
        # that's me :)
        if nuuid == gossiper.uuid:
            logger.info('KV: (get) My job to find %s' % key, part='kv')
            v = self.get(key)
            return v
        else:
            logger.info('KV: another node is managing %s' % ukey)
            n = gossiper.get(nuuid)
            # Maybe the node disapears, if so bailout and say we got no luck
            if n is None:
                return None
            uri = 'http://%s:%s/kv/%s' % (n['addr'], n['port'], ukey)
            try:
                logger.info('KV: (get) relaying to %s: %s' % (n['name'], uri), part='kv')
                r = rq.get(uri)
                if r.status_code == 404:
                    logger.info("GET KEY %s return a 404" % ukey, part='kv')
                    return None
                logger.info('KV: get founded (%d)' % len(r.text), part='kv')
                return r.text
            except HTTP_EXCEPTIONS, exp:
                logger.error('KV: error asking to %s: %s' % (n['name'], str(exp)), part='kv')
                return None
    
    
    # main method to export http interface. Must be in a method that got
    # a self entry
    def export_http(self):
        @route('/kv/')
        @route('/kv')
        def list_keys():
            response.content_type = 'application/json'
            l = list(self.db.RangeIter(include_value=False))
            return json.dumps(l)
        
        
        @route('/kv-meta/changed/:t', method='GET')
        def changed_since(t):
            response.content_type = 'application/json'
            t = int(t)
            return json.dumps(self.changed_since(t))
        
        
        @route('/kv/:ukey#.+#', method='GET')
        def interface_GET_key(ukey):
            t0 = time.time()
            logger.debug("GET KEY %s" % ukey, part='kv')
            v = self.get_key(ukey)
            if v is None:
                logger.debug("GET KEY %s return a 404" % ukey, part='kv')
                abort(404, '')
            logger.debug("GET: get time %s" % (time.time() - t0), part='kv')
            return v
        
        
        @route('/kv/:ukey#.+#', method='DELETE')
        def interface_DELETE_key(ukey):
            logger.debug("KV: DELETE KEY %s" % ukey, part='kv')
            self.delete_key(ukey)


kvmgr = KVBackend()
