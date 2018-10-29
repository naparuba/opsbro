import ssl

try:
    from httplib import HTTPException
except ImportError:
    from http.client import HTTPException
from socket import error as SocketError

try:
    from urllib2 import Request, build_opener, URLError, HTTPError, HTTPHandler, HTTPPasswordMgrWithDefaultRealm, HTTPBasicAuthHandler, HTTPSHandler
except ImportError:
    from urllib.request import Request, build_opener, HTTPHandler, HTTPPasswordMgrWithDefaultRealm, HTTPBasicAuthHandler, HTTPSHandler
    from urllib.error import URLError, HTTPError

try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode

_HTTP_EXCEPTIONS = None

from .jsonmgr import jsoner
from .util import unicode_to_bytes


def get_http_exceptions():
    global _HTTP_EXCEPTIONS
    if _HTTP_EXCEPTIONS is not None:
        return _HTTP_EXCEPTIONS
    HTTP_EXCEPTIONS = (HTTPError, URLError, SocketError, HTTPException)
    _HTTP_EXCEPTIONS = HTTP_EXCEPTIONS
    return _HTTP_EXCEPTIONS


class Httper(object):
    def __init__(self):
        # NOTE: ssl.SSLContext is only availabe on last python 2.7 versions
        if hasattr(ssl, 'SSLContext'):
            # NOTE: was before, but seems to be not as large as default context
            ## self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
            self.ssl_context = ssl.create_default_context()
            self.ssl_context.options &= ~ssl.OP_NO_SSLv3  # reenable SSLv3 if need
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE
        else:
            self.ssl_context = None
    
    
    def get(self, uri, params={}, headers={}, with_status_code=False, timeout=10, user=None, password=None):
        data = None  # always none in GET
        
        if params:
            uri = "%s?%s" % (uri, urlencode(params))
        
        # SSL, user/password and basic
        # NOTE: currently don't manage ssl & user/password
        if uri.startswith('https://'):
            handler = HTTPSHandler(context=self.ssl_context)
        elif user and password:
            passwordMgr = HTTPPasswordMgrWithDefaultRealm()
            passwordMgr.add_password(None, uri, user, password)
            handler = HTTPBasicAuthHandler(passwordMgr)
        else:
            handler = HTTPHandler
        
        url_opener = build_opener(handler)
        
        req = Request(uri, data)
        req.get_method = lambda: 'GET'
        for (k, v) in headers.items():
            req.add_header(k, v)
        
        request = url_opener.open(req, timeout=timeout)
        
        response = request.read()
        status_code = request.code
        request.close()
        
        if not with_status_code:
            return response
        else:
            return (status_code, response)
    
    
    @staticmethod
    def delete(uri, params={}, headers={}):
        data = None  # always none in GET
        
        if params:
            uri = "%s?%s" % (uri, urlencode(params))
        
        url_opener = build_opener(HTTPHandler)
        
        req = Request(uri, data)
        req.get_method = lambda: 'DELETE'
        for (k, v) in headers.items():
            req.add_header(k, v)
        request = url_opener.open(req)
        response = request.read()
        # code = request.code
        return response
    
    
    @staticmethod
    def post(uri, params={}, headers={}):
        data = None  # always none in GET
        
        if params:
            # TODO: sure it's json and not urlencode?
            # data = urlencode(params)
            data = unicode_to_bytes(jsoner.dumps(params))
        
        url_opener = build_opener(HTTPHandler)
        
        req = Request(uri, data)
        req.get_method = lambda: 'POST'
        for (k, v) in headers.items():
            req.add_header(k, v)
        request = url_opener.open(req)
        response = request.read()
        # code = request.code
        return response
    
    
    @staticmethod
    def put(uri, data=None, params={}, headers=None):
        # data = None  # always none in GET
        if headers is None:
            headers = {}
        
        if params:
            # TODO: sure it's json and not urlencode?
            # data = urlencode(params)
            uri = "%s?%s" % (uri, urlencode(params))
            headers['Content-Type'] = 'your/contenttype'
        
        url_opener = build_opener(HTTPHandler)
        
        req = Request(uri, data)
        req.get_method = lambda: 'PUT'
        for (k, v) in headers.items():
            req.add_header(k, v)
        request = url_opener.open(req)
        response = request.read()
        # code = request.code
        return response


httper = Httper()
