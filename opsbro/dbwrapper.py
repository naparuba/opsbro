from .log import logger


class SqliteDB(object):
    def __init__(self, path):
        from .misc.sqlitedict import SqliteDict
        self.db = SqliteDict(path+'.sqlite', autocommit=True)
    
    
    def Get(self, key, fill_cache=False):
        return self.db[key]
    
    
    def Put(self, key, value):
        self.db[key] = value
    
    
    def GetStats(self):
        return 'No stats from sqlitedb'


class DBWrapper(object):
    def __init__(self):
        # only import leveldb when need
        self.leveldb = None
    
    
    # Want a database, if we can we ty leveldb, if not, fallback to sqlite
    def get_db(self, path):
        if self.leveldb is None:
            try:
                import leveldb
                self.leveldb = leveldb
            except ImportError:
                self.leveldb = None
        if self.leveldb:
            logger.info('Opening KV database at path %s' % path)
            db = self.leveldb.LevelDB(path)
            logger.info('KV database at path %s is opened: %s' % (path, db))
            return db
        logger.info('Librairy leveldb is missing, falling back to sqlite db backend.')
        return SqliteDB(path)


dbwrapper = DBWrapper()
