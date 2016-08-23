try:
    import leveldb
except ImportError:
    leveldb = None


class FakeDB(object):
    def __init__(self):
        pass
    
    
    def Get(self, key, fill_cache=False):
        return ''
    
    
    def Put(self, key, value):
        return


class DBWrapper():
    def __init__(self):
        pass
    
    
    def get_db(self, path):
        if leveldb:
            db = leveldb.LevelDB(path)
            return db
        return FakeDB()


dbwrapper = DBWrapper()
