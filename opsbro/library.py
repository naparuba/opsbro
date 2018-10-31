class LibraryStore(object):
    def __init__(self):
        self.__encrypter = None
        self.__requests = None
        self.__jinja2 = None
        self.__pprint = None
        self.__pygments = None
        self.__StringIO = None
        self.__StringIO_unicode = None  # unicode compliant version
    
    
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
    
    
    def get_jinja2(self):
        if self.__jinja2 is not None:
            return self.__jinja2
        try:
            import jinja2
            self.__jinja2 = jinja2
        except Exception:
            self.__jinja2 = None
        return self.__jinja2
    
    
    def get_pprint(self):
        if self.__pprint is not None:
            return self.__pprint
        import pprint
        self.__pprint = pprint
        return self.__pprint
    
    
    def get_pygments(self):
        if self.__pygments is not None:
            return self.__pygments
        # try pygments for pretty printing if available
        try:
            import pygments
            import pygments.lexers
            import pygments.formatters
        except ImportError:
            pygments = None
        self.__pygments = pygments
        return self.__pygments
    
    
    def get_StringIO(self):
        if self.__StringIO is not None:
            return self.__StringIO
        try:
            from cStringIO import StringIO
        except ImportError:  # Python3
            from io import StringIO
        self.__StringIO = StringIO
        return self.__StringIO
    
    
    def get_StringIO_unicode_compatible(self):
        if self.__StringIO_unicode is not None:
            return self.__StringIO_unicode
        try:
            from StringIO import StringIO
        except ImportError:  # Python3
            from io import StringIO
        self.__StringIO_unicode = StringIO
        return self.__StringIO_unicode


libstore = LibraryStore()
