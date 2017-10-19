import os
import json
import socket
import urllib2
import urllib
import httplib
from urlparse import urlsplit

from opsbro.library import libstore

_HTTP_EXCEPTIONS = None


def get_http_exceptions():
    global _HTTP_EXCEPTIONS
    if _HTTP_EXCEPTIONS is not None:
        return _HTTP_EXCEPTIONS
    rq = libstore.get_requests()
    # Some old requests libs do not have rq.packages.urllib3 and direclty map them to rq.exceptions.RequestException
    # like in ubuntu 14.04 version
    if hasattr(rq, 'packages'):
        HTTP_EXCEPTIONS = (rq.exceptions.RequestException, rq.packages.urllib3.exceptions.HTTPError, urllib2.HTTPError)
    else:
        HTTP_EXCEPTIONS = (rq.exceptions.RequestException, urllib2.HTTPError)
    _HTTP_EXCEPTIONS = HTTP_EXCEPTIONS
    return _HTTP_EXCEPTIONS


class Httper(object):
    def __init__(self):
        pass
    
    
    @staticmethod
    def get(uri, params={}, headers={}):
        data = None  # always none in GET
        
        if params:
            uri = "%s?%s" % (uri, urllib.urlencode(params))
        
        url_opener = urllib2.build_opener(urllib2.HTTPHandler)
        
        req = urllib2.Request(uri, data)
        req.get_method = lambda: 'GET'
        for (k, v) in headers.iteritems():
            req.add_header(k, v)
        request = url_opener.open(req)
        response = request.read()
        # code = request.code
        # if code != 200:
        #    raise urllib2.HTTPError('')
        return response
    
    
    @staticmethod
    def delete(uri, params={}, headers={}):
        data = None  # always none in GET
        
        if params:
            uri = "%s?%s" % (uri, urllib.urlencode(params))
        
        url_opener = urllib2.build_opener(urllib2.HTTPHandler)
        
        req = urllib2.Request(uri, data)
        req.get_method = lambda: 'DELETE'
        for (k, v) in headers.iteritems():
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
        
        url_opener = urllib2.build_opener(urllib2.HTTPHandler)
        
        req = urllib2.Request(uri, data)
        req.get_method = lambda: 'POST'
        for (k, v) in headers.iteritems():
            req.add_header(k, v)
        request = url_opener.open(req)
        response = request.read()
        # code = request.code
        return response


httper = Httper()
