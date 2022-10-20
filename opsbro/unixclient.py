#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com


import os
import socket
import sys

PY3 = sys.version_info >= (3,)

try:  # Python 2
    from urllib2 import AbstractHTTPHandler, Request, build_opener, URLError, HTTPHandler
except ImportError:  # Python 3
    from urllib.request import AbstractHTTPHandler, Request, build_opener, HTTPHandler
    from urllib.error import URLError
try:  # Python 2
    from httplib import HTTPConnection, BadStatusLine
except ImportError:  # Python 3
    from http.client import HTTPConnection, BadStatusLine

try:  # Python2
    from urllib import urlencode, quote, quote_plus
except ImportError:
    from urllib.parse import urlencode, quote, quote_plus

try:  # Python 2
    from urlparse import urlsplit, urlunsplit
except ImportError:
    from urllib.parse import urlsplit, urlunsplit

from .log import logger, cprint
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
    
    
    # IMPORTANT: this will transform IRI (url with utf8) into real URL with % encoded values
    def _iri2uri(self, iri):
        if not PY3:
            cprint(u'_iri2uri:: start  uri=%s(type=%s)' % (iri, type(iri)))
            if isinstance(iri, str):
                iri = iri.decode('utf8')
            cprint(u'_iri2uri:: postdecode  uri=%s(type=%s)' % (iri, type(iri)))
            # PY2 version:
            (scheme, netloc, path, query, fragment) = urlsplit(iri)
            cprint(u'_iri2uri:: parsed_path=%s(type=%s)' % (path, type(path)))
            scheme = quote(scheme)
            netloc = netloc.encode('idna').decode('utf-8')
            # IMPORTANT: the quote need bytes
            if not isinstance(path, str):
                path = path.encode('utf8')
            # NOP: we cannot print it now it's bytes cprint(u'_iri2uri:: post_decode=%s(type=%s)' % (path, type(path)))
            try:
                n_path = quote(path)
            except KeyError:
                cprint(u'ARG: %s(%s) and path=(%s)' % (iri, type(iri), type(path)))
                raise
            # query = quote(query)  # already quote
            fragment = quote(fragment)
            uri = urlunsplit((scheme, netloc, n_path, query, fragment))
            return uri
        
        # PY3 version:
        (scheme, netloc, path, query, fragment) = urlsplit(iri)
        scheme = quote(scheme)
        netloc = netloc.encode('idna').decode('utf-8')
        path = quote(path)
        # query = quote(query)  # already quote
        fragment = quote(fragment)
        uri = urlunsplit((scheme, netloc, path, query, fragment))
        return uri
    
    
    def unix_open(self, req):
        full_path = u"%s%s" % urlsplit(req.get_full_url())[1:3]
        path = os.path.sep
        unix_socket = ''
        for part in full_path.split("/"):
            path = os.path.join(path, part)
            if not os.path.exists(path):
                break
            unix_socket = path
        
        # add a host or else urllib complains
        try:
            url = 'blabla'
            _req_data = self.__get_req_data(req)
            _iri = bytes_to_unicode(req.get_full_url().replace(unix_socket, u'/localhost'))
            url = self._iri2uri(_iri)
            new_req = Request(url, _req_data, dict(req.header_items()))
            new_req.timeout = req.timeout
            new_req.get_method = req.get_method  # Also copy specific method from the original header
            # return self.do_open(UnixHTTPConnection(unix_socket), new_req)
            cprint(u'UnixSocketHandler:: unix_open :: url="%s" / req_data="%s"   new_req=%s' % (url, _req_data, new_req.__dict__))
            r = self.do_open(UnixHTTPConnection(unix_socket), new_req)
        except UnicodeEncodeError as exp:
            raise
        #            raise Exception('%s : context: url=%s(%s), iri=%s(%s)' % (exp, url, type(url), _iri, type(_iri)))
        
        return r
    
    
    unix_request = AbstractHTTPHandler.do_request_


def to_unicode_recursive_obj(in_obj):
    
    def encode_list(in_list):
        out_list = []
        for el in in_list:
            out_list.append(to_unicode_recursive_obj(el))
        return out_list
    
    
    def encode_dict(in_dict):
        out_dict = {}
        for k, v in in_dict.items():
            out_dict[k] = to_unicode_recursive_obj(v)
        return out_dict
    
    
    if not PY3:
        if isinstance(in_obj, unicode):
            return in_obj.encode('utf-8')
    else:
        if isinstance(in_obj, bytes):
            return in_obj.encode('utf-8')
    if isinstance(in_obj, list):
        return encode_list(in_obj)
    elif isinstance(in_obj, tuple):
        return tuple(encode_list(in_obj))
    elif isinstance(in_obj, dict):
        return encode_dict(in_obj)
    
    return in_obj


# Get on the local socket. Beware of monkeypatch the get
def get_local(u, local_socket, params={}, method=u'GET', timeout=10):
    UnixHTTPConnection.socket_timeout = timeout
    data = None
    special_headers = []
    
    as_unicode_params = to_unicode_recursive_obj(params)
    
    if method == u'GET' and as_unicode_params:
        u = u"%s?%s" % (u, urlencode(as_unicode_params))
    if method == u'POST' and params:
        data = unicode_to_bytes(urlencode(as_unicode_params))
    if method == u'PUT' and as_unicode_params:
        special_headers.append((u'Content-Type', 'application/octet-stream'))
        data = unicode_to_bytes(as_unicode_params)
    
    # not the same way to connect
    # * windows: TCP
    # * unix   : unix socket
    if os.name == 'nt':
        url_opener = build_opener(HTTPHandler)
        uri = u'http://127.0.0.1:6770%s' % u
    else:  # unix
        url_opener = build_opener(UnixSocketHandler())
        uri = u'unix:/%s%s' % (local_socket, u)
    cprint(u'CALLING: uri type=%s' % type(uri))
    cprint(u'CALLING: %s:%s' % (method, uri))
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
        logger.debug(u"ERROR local unix get json raw return did raise an exception %s" % exp)
        raise
    
    # From bytes to string
    r = bytes_to_unicode(r)
    
    if r == '':
        return r
    # logger.debug("local unix get json raw return %s" % r)
    
    if multi and u"}{" in r:  # docker api sometimes returns juxtaposed json dictionaries
        r = u"[{0}]".format(r.replace(u"}{", "},{"))
    
    try:
        d = jsoner.loads(r)
    except Exception as exp:  # bad json
        logger.debug(u"ERROR local unix get json raw return did raise an exception  in bad json (%s) %s" % (r, exp))
        logger.error(u'Bad return from the server %s: "%s"' % (exp, r))
        raise
    return d
