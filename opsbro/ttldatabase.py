import shutil
import os
import time
import threading
import codecs

from .now import NOW
from .stats import STATS
from .threadmgr import threader
from .dbwrapper import dbwrapper
from .log import LoggerFactory
from .stop import stopper

# Global logger for this part
logger = LoggerFactory.create_logger('key-value')


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
        threader.create_and_launch(self.ttl_cleaning_thread, name='Cleaning TTL expired key/values', essential=True, part='key-value')
    
    
    # Load the hour ttl/H base where we will save all master
    # key for the H hour
    def get_ttl_db(self, h):
        cdb = self.dbs.get(h, None)
        # If missing, look to load it but with a lock to be sure we load it only once
        if cdb is None:
            STATS.incr('ttl-db-cache-miss', 1)
            with self.lock:
                # Maybe during the lock get one other thread succedd in getting the cdb
                if h not in self.dbs:
                    # Ok really load it, but no more than self.db_cache_size
                    # databases (number of open files can increase quickly)
                    if len(self.dbs) > self.db_cache_size:
                        ttodrop = self.dbs.keys()[0]
                        ttodrop.close()
                        del self.dbs[ttodrop]
                    _t = time.time()
                    cdb = codecs.open(os.path.join(self.ttldb_dir, '%d.ttl' % h), 'a', 'utf8')
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
        logger.debug("TTL save", key, "with ttl", ttl_t, "in", cdb)
        cdb.write(key)
        cdb.write('\n')
        cdb.flush()
    
    
    # We already droped all entry in a db, so drop it from our cache
    def drop_db(self, h):
        # now remove the database
        with self.lock:
            if h in self.dbs:
                self.dbs[h].close()
                del self.dbs[h]
        
        # And remove the files of this database
        ttl_path = os.path.join(self.ttldb_dir, '%d.ttl' % h)
        if os.path.exists(ttl_path):
            logger.info("Deleting ttl database tree : %s" % ttl_path)
            os.unlink(ttl_path)
    
    
    # Look at the available dbs and clean all olds dbs that time are lower
    # than current hour
    def clean_old(self):
        from .kv import kvmgr  # avoid recursive import
        
        logger.debug("TTL clean old")
        now = NOW.now + 3600
        h = divmod(now, 3600)[0] * 3600
        # Look at the databses directory that have the hour time set
        subdirs = os.listdir(self.ttldb_dir)
        
        for d in subdirs:
            # Sub files can be:
            # * EPOCH.sqlite => was a sqlite file
            # * EPOCH => is a leveldb dir
            if d.endswith('.ttl'):
                d = d.replace('.ttl', '')
            try:
                bhour = int(d)
            except ValueError:  # who add a dir that is not a int here...
                continue
            # Is the hour available for cleaning?
            if bhour < h:
                before = time.time()
                logger.info("TTL bhour is too low: cleaning %s" % bhour)
                # take the database and dump all keys in it
                f = codecs.open(os.path.join(self.ttldb_dir, '%d.ttl' % bhour), 'r', 'utf8')
                nb_clean = 0
                for line in f.readlines():
                    key = line.strip()
                    nb_clean += 1
                    kvmgr.delete(key)
                
                # now we clean all old entries, remove the idx database
                self.drop_db(bhour)
                logger.info("TTL bhour %s was used to clean %d keys in %.2fs" % (bhour, nb_clean, time.time() - before))
    
    
    # Thread that will manage the delete of the ttld-die key
    def ttl_cleaning_thread(self):
        while not stopper.is_stop():
            time.sleep(5)
            self.clean_old()
