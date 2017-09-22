class LibraryStore(object):
    def __init__(self):
        self.__encrypter = None
        self.__requests = None
    
    
    def get_encrypter(self):
        if self.__encrypter is not None:
            return self.__encrypter
        from opsbro.encrypter import get_encrypter
        self.__encrypter = get_encrypter()
        return self.__encrypter
    
    
    def get_requests(self):
        if self.__requests is not None:
            return self.__requests
        import requests
        self.__requests = requests
        return self.__requests


libstore = LibraryStore()
