#!/usr/bin/env python

# -*- coding: utf-8 -*-

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com


import os
import sys
import base64
import uuid
import time
import json
import socket
import urllib2
import urllib
import httplib
from urlparse import urlsplit
try:
    import requests as rq
except ImportError:
    rq = None

from kunai.log import cprint, logger



#### For local socket handling
DEFAULT_SOCKET_TIMEOUT = 5

# Class used in conjuction with UnixSocketHandler to make urllib2
# compatible with Unix sockets.
class UnixHTTPConnection(httplib.HTTPConnection):

    socket_timeout = DEFAULT_SOCKET_TIMEOUT

    def __init__(self, unix_socket):
        self._unix_socket = unix_socket

    def connect(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self._unix_socket)
        sock.settimeout(self.socket_timeout)
        self.sock = sock

    def __call__(self, *args, **kwargs):
        httplib.HTTPConnection.__init__(self, *args, **kwargs)
        return self


# Class that makes Unix sockets work with urllib2 without any additional
# dependencies.
class UnixSocketHandler(urllib2.AbstractHTTPHandler):
    def unix_open(self, req):
        full_path = "%s%s" % urlsplit(req.get_full_url())[1:3]
        path = os.path.sep
        unix_socket = ''
        for part in full_path.split("/"):
            path = os.path.join(path, part)
            if not os.path.exists(path):
                break
            unix_socket = path

        # add a host or else urllib2 complains
        url = req.get_full_url().replace(unix_socket, "/localhost")
        new_req = urllib2.Request(url, req.get_data(), dict(req.header_items()))
        new_req.timeout = req.timeout
        return self.do_open(UnixHTTPConnection(unix_socket), new_req)

    unix_request = urllib2.AbstractHTTPHandler.do_request_



request_errors = (urllib2.URLError, rq.exceptions.ConnectionError, )




# Get on the local socket. Beware to monkeypatch the get
def get_local(u, local_socket, params={}):
    UnixHTTPConnection.socket_timeout = 5
    url_opener = urllib2.build_opener(UnixSocketHandler())
    p = local_socket
    if params:
        u = "%s?%s" % (u, urllib.urlencode(params))
    uri = 'unix:/%s%s' % (p, u)
    logger.debug("Connecting to local http unix socket at: %s" % uri)
    req = urllib2.Request(uri, None)
    request = url_opener.open(req)
    response = request.read()
    code = request.code
    return (code, response)


# get a json on the local server, and parse the result    
def get_json(uri, local_socket='', params={}, multi=False):
    try:
        (code, r) = get_local(uri, local_socket=local_socket, params=params)
    except request_errors, exp:
        raise

    if r == '':
        return r
    logger.debug("local unix get json raw return", r)

    if multi and "}{" in r: # docker api sometimes returns juxtaposed json dictionaries
        r = "[{0}]".format(r.replace("}{", "},{"))
        
    try:
        d = json.loads(r) # was r.text from requests
    except ValueError, exp:# bad json
        logger.error('Bad return from the server %s' % exp)
        raise
    return d
