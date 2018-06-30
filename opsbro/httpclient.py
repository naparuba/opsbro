import json
import urllib

try:
    from httplib import HTTPException
except ImportError:
    from http.client import HTTPException
from socket import error as SocketError

try:
    from urllib2 import Request, build_opener, URLError, HTTPError, HTTPHandler, HTTPPasswordMgrWithDefaultRealm, HTTPBasicAuthHandler
except ImportError:
    from urllib.request import Request, build_opener, HTTPHandler, HTTPPasswordMgrWithDefaultRealm, HTTPBasicAuthHandler
    from urllib.error import URLError, HTTPError

_HTTP_EXCEPTIONS = None


def get_http_exceptions():
    global _HTTP_EXCEPTIONS
    if _HTTP_EXCEPTIONS is not None:
        return _HTTP_EXCEPTIONS
    HTTP_EXCEPTIONS = (HTTPError, URLError, SocketError, HTTPException)
    _HTTP_EXCEPTIONS = HTTP_EXCEPTIONS
    return _HTTP_EXCEPTIONS


class Httper(object):
    def __init__(self):
        pass
    
    
    @staticmethod
    def get(uri, params={}, headers={}, with_status_code=False, timeout=10, user=None, password=None):
        data = None  # always none in GET
        
        if params:
            uri = "%s?%s" % (uri, urllib.urlencode(params))
        
        if user and password:
            handler = HTTPHandler
        else:
            passwordMgr = HTTPPasswordMgrWithDefaultRealm()
            passwordMgr.add_password(None, uri, user, password)
            handler = HTTPBasicAuthHandler(passwordMgr)
        
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
            uri = "%s?%s" % (uri, urllib.urlencode(params))
        
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
            # data = urllib.urlencode(params)
            data = json.dumps(params)
        
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
            # data = urllib.urlencode(params)
            uri = "%s?%s" % (uri, urllib.urlencode(params))
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
