from opsbro.log import logger


class FakeDB(object):
    def __init__(self):
        pass
    
    
    def Get(self, key, fill_cache=False):
        logger.error('Fake call to KV store, please install leveldb')
        return ''
    
    
    def Put(self, key, value):
        logger.error('Fake call to KV store, please install leveldb')
        return
    
    
    def GetStats(self):
        return ''


class DBWrapper(object):
    def __init__(self):
        # only import leveldb when need
        self.leveldb = None
        self.is_leveldb_lib_imported = False
    
    
    def get_db(self, path):
        if not self.is_leveldb_lib_imported:
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
        logger.error('Libriry leveldb is missing, you cannot save KV values.')
        return FakeDB()


dbwrapper = DBWrapper()
