try:
    import leveldb
except ImportError:
    leveldb = None
from kunai.log import logger

class FakeDB(object):
    def __init__(self):
        pass
    
    
    def Get(self, key, fill_cache=False):
        logger.error('Fake call to KV store, please install leveldb')
        return ''
    
    
    def Put(self, key, value):
        logger.error('Fake call to KV store, please install leveldb')
        return


class DBWrapper():
    def __init__(self):
        pass
    
    
    def get_db(self, path):
        if leveldb:
            logger.info('Opening KV database at path %s' % path)
            db = leveldb.LevelDB(path)
            logger.info('KV database at path %s is opened: %s' % (path, db))
            return db
        logger.error('Libriry leveldb is missing, you cannot save KV values.')
        return FakeDB()


dbwrapper = DBWrapper()
