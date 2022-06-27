#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com


import os
import socket

try:  # Python 2
    from urllib2 import AbstractHTTPHandler, Request, build_opener, URLError, HTTPHandler
except ImportError:  # Python 3
    from urllib.request import AbstractHTTPHandler, Request, build_opener, HTTPHandler
    from urllib.error import URLError
try:  # Python 2
    from httplib import HTTPConnection, BadStatusLine
except ImportError:  # Python 3
    from http.client import HTTPConnection, BadStatusLine

try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode

try:  # Python 2
    from urlparse import urlsplit
except ImportError:
    from urllib.parse import urlsplit

from .log import logger
from .jsonmgr import jsoner
from .util import unicode_to_bytes, bytes_to_unicode

#### For local socket handling
DEFAULT_SOCKET_TIMEOUT = 5


# Class used in conjuction with UnixSocketHandler to make urllib
# compatible with Unix sockets.
class UnixHTTPConnection(HTTPConnection):
    socket_timeout = DEFAULT_SOCKET_TIMEOUT
    
    
    def __init__(self, unix_socket):
        self._unix_socket = unix_socket
    
    
    def connect(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self._unix_socket)
        sock.settimeout(self.socket_timeout)
        self.sock = sock
    
    
    def __call__(self, *args, **kwargs):
        HTTPConnection.__init__(self, *args, **kwargs)
        return self


# Class that makes Unix sockets work with urllib without any additional
# dependencies.
class UnixSocketHandler(AbstractHTTPHandler):
    
    @staticmethod
    def __get_req_data(req):
        # Python 2:
        if hasattr(req, 'get_data'):
            return req.get_data()
        # Python 3
        return req.data
    
    
    def unix_open(self, req):
        full_path = "%s%s" % urlsplit(req.get_full_url())[1:3]
        path = os.path.sep
        unix_socket = ''
        for part in full_path.split("/"):
            path = os.path.join(path, part)
            if not os.path.exists(path):
                break
            unix_socket = path
        
        # add a host or else urllib complains
        url = req.get_full_url().replace(unix_socket, "/localhost")
        new_req = Request(url, self.__get_req_data(req), dict(req.header_items()))
        new_req.timeout = req.timeout
        new_req.get_method = req.get_method  # Also copy specific method from the original header
        return self.do_open(UnixHTTPConnection(unix_socket), new_req)
    
    
    unix_request = AbstractHTTPHandler.do_request_


# Get on the local socket. Beware to monkeypatch the get
def get_local(u, local_socket, params={}, method='GET', timeout=10):
    UnixHTTPConnection.socket_timeout = timeout
    data = None
    special_headers = []
    
    if method == 'GET' and params:
        u = u"%s?%s" % (u, urlencode(params))
    if method == 'POST' and params:
        data = unicode_to_bytes(urlencode(params))
    if method == 'PUT' and params:
        special_headers.append(('Content-Type', 'application/octet-stream'))
        data = unicode_to_bytes(params)
    
    # not the same way to connect
    # * windows: TCP
    # * unix   : unix socket
    if os.name == 'nt':
        url_opener = build_opener(HTTPHandler)
        uri = u'http://127.0.0.1:6770%s' % u
    else:  # unix
        url_opener = build_opener(UnixSocketHandler())
        uri = u'unix:/%s%s' % (local_socket, u)
    
    logger.debug(u"Connecting to local http/unix socket at: %s with method %s" % (uri, method))
    
    req = Request(uri, data)
    req.get_method = lambda: method
    for (k, v) in special_headers:
        req.add_header(k, v)
    request = url_opener.open(req)
    response = request.read()
    code = request.code
    return (code, response)


def get_not_critical_request_errors():
    return (socket.timeout,)


def get_request_errors():
    request_errors = (URLError, socket.timeout, socket.error, BadStatusLine)
    return request_errors


# get a json on the local server, and parse the result    
def get_json(uri, local_socket='', params={}, multi=False, method='GET', timeout=10):
    
    try:
        (code, r) = get_local(uri, local_socket=local_socket, params=params, method=method, timeout=timeout)
    except get_request_errors() as exp:
        logger.debug("ERROR local unix get json raw return did raise an exception %s" % exp)
        raise
    
    # From bytes to string
    r = bytes_to_unicode(r)
    
    if r == '':
        return r
    # logger.debug("local unix get json raw return %s" % r)
    
    if multi and "}{" in r:  # docker api sometimes returns juxtaposed json dictionaries
        r = "[{0}]".format(r.replace("}{", "},{"))
    
    try:
        d = jsoner.loads(r)
    except Exception as exp:  # bad json
        logger.debug("ERROR local unix get json raw return did raise an exception  in bad json (%s) %s" % (r, exp))
        logger.error('Bad return from the server %s: "%s"' % (exp, r))
        raise
    return d
