import os

from .log import logger

leveldb_lib = None
failback_leveldb_lib = None


class SqliteDBBackend(object):
    name = 'sqlite'
    
    
    def __init__(self, path):
        self.did_error = False
        self.last_error = ''
        
        self.path = path + '.sqlite'
        from .misc.sqlitedict import SqliteDict
        self.db = SqliteDict(self.path, autocommit=True)  # , journal_mode='OFF')
    
    
    def Get(self, key, fill_cache=False):
        return self.db[key]
    
    
    def Put(self, key, value):
        try:
            self.db[key] = value
        except Exception as exp:
            err = 'The SQLite backend did raise an error: %s. On old system like centos 7.0/7.1, sqlite have stability issues, and you should switch to leveldb instead.' % exp
            self.last_error = err
            self.did_error = True
    
    
    def Delete(self, key):
        try:
            del self.db[key]
        except KeyError:  # ok, already deleted :)
            pass
    
    
    def __get_size(self):
        return os.path.getsize(self.path)
    
    
    def GetStats(self):
        return {'size': self.__get_size(), 'raw': 'No stats from sqlitedb', 'error': self.last_error}


class FailbackLevelDBBackend(object):
    name = 'leveldb'
    
    
    def __init__(self, path):
        self.path = path
        logger.info('[Failback leveldb] Opening KV database at path %s' % path)
        self.db = failback_leveldb_lib.DB(path, create_if_missing=True)
        logger.info('[Failback leveldb] KV database at path %s is opened: %s' % (path, self.db))
    
    
    def Get(self, key, fill_cache=False):
        v = self.db.get(key, fill_cache=fill_cache)
        if v is None:
            raise KeyError()
        return v
    
    
    def Put(self, key, value):
        self.db.put(key, value)
    
    
    def Delete(self, key):
        self.db.delete(key)
    
    
    def __get_size(self):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(self.path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
                logger.info('ADD: %s %d' % (fp, os.path.getsize(fp)))
        return total_size
    
    
    def GetStats(self):
        return {'size': self.__get_size(), 'raw': 'no stats', 'error': ''}


class LevelDBBackend(object):
    name = 'leveldb'
    
    
    def __init__(self, path):
        self.path = path
        logger.info('Opening KV database at path %s' % path)
        self.db = leveldb_lib.LevelDB(path)
        logger.info('KV database at path %s is opened: %s' % (path, self.db))
    
    
    def Get(self, key, fill_cache=False):
        return self.db.Get(key, fill_cache=fill_cache)
    
    
    def Put(self, key, value):
        self.db.Put(key, value)
    
    
    def Delete(self, key):
        self.db.Delete(key)
    
    
    def __get_size(self):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(self.path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
                logger.info('ADD: %s %d' % (fp, os.path.getsize(fp)))
        return total_size
    
    
    def GetStats(self):
        return {'size': self.__get_size(), 'raw': self.db.GetStats(), 'error': ''}


class DBWrapper(object):
    def __init__(self):
        # only import leveldb when need
        self.leveldb = None
    
    
    # Want a database, if we can we ty leveldb, if not, fallback to sqlite
    def get_db(self, path):
        global leveldb_lib, failback_leveldb_lib
        
        # Try native leveldb lib
        if leveldb_lib is None:
            try:
                import leveldb
                leveldb_lib = leveldb
            except ImportError:
                leveldb_lib = None
        if leveldb_lib:
            return LevelDBBackend(path)
        
        # Then failback one
        if failback_leveldb_lib is None:
            try:
                from .misc.internalleveldb import leveldb
                failback_leveldb_lib = leveldb
            except ImportError:
                failback_leveldb_lib = None
        if failback_leveldb_lib:
            return FailbackLevelDBBackend(path)
        
        logger.info('Librairy leveldb is missing, falling back to sqlite db backend.')
        return SqliteDBBackend(path)


dbwrapper = DBWrapper()
