#!/usr/bin/env python
# coding=utf-8

# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com
import json
import traceback

import requests
import requests_unixsocket

from flask import Flask, abort, request
from flask import request as flask_request

app = Flask(__name__)

requests_unixsocket.monkeypatch()

try:  # Python2
    from urllib import unquote
except ImportError:
    from urllib.parse import unquote

from opsbro_test import *

from opsbro.cli import post_opsbro_json, put_opsbro_json
# from opsbro.httpdaemon import httpdaemon, response, request, abort
from opsbro.jsonmgr import jsoner
from opsbro.threadmgr import threader
from opsbro.unixclient import get_local, get_json
from opsbro.util import bytes_to_unicode, unicode_to_bytes, PY3
from opsbro.log import cprint

# make http_export call directly app.route with all args:
http_export = app.route

# if not PY3:
#    bytes = str

SOCKET_PATH = '/tmp/test_unix_socket.sock'


#### Pour lancer le test:
# test/docker_run.sh test   docker-file-CENTOS-7-installation-centos7.9.txt
# yum install -y python-requests;cd test/;python test_unixclient.py  TestUnixClient.test_unixclient_POST_simple_ret_utf8_arg_utf8_REQUESTS
# test/docker_run.sh test docker-file-ALPINE-alpine3.16.txt
# apk add py3-flask;apk add py3-requests;cd test/;python3 test_unixclient.py TestUnixClient.test_unixclient_GET_simple_ret_utf8_arg_utf8_REQUESTS

def fake_get_local_socket():
    cprint('FAKING: %s' % SOCKET_PATH)
    return SOCKET_PATH


opsbro.cli.get_local_socket = fake_get_local_socket

RES_ASCII = {u'res': u'OK'}
RES_UTF8 = {u'rés': u'öK'}

ARG_ASCII_KEY = u'arg'
ARG_ASCII_VALUE = u'value'
ARG_ASCII = {ARG_ASCII_KEY: ARG_ASCII_VALUE}

ARG_UTF8_KEY = u'ärg'
ARG_UTF8_VALUE = u'valué'
ARG_UTF8 = {ARG_UTF8_KEY: ARG_UTF8_VALUE}

VALUE_ONLY_UTF8_KEY = u'arg'
VALUE_ONLY_UTF8_VALUE = u'valué'
VALUE_ONLY_UTF8 = {VALUE_ONLY_UTF8_KEY: VALUE_ONLY_UTF8_VALUE}


def get_from_POST(req, arg_name):
    if 'dict' not in req.POST.__dict__:
        raise Exception('Cannot find dict in %s' % req.POST.__dict__)
    for (k, v) in req.POST.__dict__['dict'].items():
        print(f'get_from_POST:: comparing: {k}({type(k)}) <=> {arg_name}')
        if not PY3:
            k = bytes_to_unicode(k)
        if k != arg_name:
            print(' SKIP: %s' % k)
            continue
        if isinstance(v, list) and len(v) != 0:
            v = bytes_to_unicode(v[0])
        cprint(u'_generic_POST:: POST.get :: %s(%s) -> %s(%s)' % (k, type(k), v, type(v)))
        return v
    return None


def get_from_GET(req, arg_name):
    cprint(u'[SERVER][FLASK] raw get: %s' % flask_request.args)
    v = flask_request.args.get(arg_name, None)
    cprint(u'[SERVER][FLASK] raw get: %s -> %s' % (arg_name, v))
    return v
    if 'dict' not in req.GET.__dict__:
        raise Exception('Cannot find dict in %s' % req.GET.__dict__)
    for (k, v) in req.GET.__dict__['dict'].items():
        orig_k = k
        if not PY3:
            k = bytes_to_unicode(k)
        cprint('get_from_GET:: comparing: %s(->%s)(force=%s) <=> %s' % (orig_k, k, bytes_to_unicode(k), arg_name))
        if k != arg_name:
            print(' SKIP: %s' % k)
            continue
        if isinstance(v, list) and len(v) != 0:
            v = bytes_to_unicode(v[0])
        cprint(u'_generic_GET:: GET.get :: %s(%s) -> %s(%s)' % (k, type(k), v, type(v)))
        return v
    return None


class TestUnixClient(OpsBroTest):
    
    @classmethod
    def setUpClass(cls):
        cprint('Creating test %s' % cls)
        
        
        def _check_uri_call(expected_value, res, call_name, value):
            cprint(u'/%s: ARGS: Expected=%s Received=%s' % (call_name, type(expected_value), type(value)))
            cprint(u'/%s: ARGS: %s (type=%s)' % (call_name, value, type(value)))
            if type(expected_value) != type(value):  # ok, we don't have the same type, we are doom to fail
                return abort(500, u'[%s] Bad type between expected value %s(%s)  and received one %s(%s)' % (
                    call_name, expected_value, type(expected_value), value, type(value)))
            if value == expected_value:
                return jsoner.dumps(res)
            return abort(500, u'bad value for %s: %s' % (call_name, value))
        
        
        def _generic_call(key_name, key_value, res, call_name, value):
            cprint(u'/%s: ARGS: Expected=%s Received=%s' % (call_name, type(key_value), type(value)))
            cprint(u'/%s: ARGS: %s=%s (type=%s)' % (call_name, key_name, value, type(value)))
            if type(value) != type(key_value):  # ok, we don't have the same type, we are doom to fail
                return abort(500, u'[%s] Bad type between received value %s=%s(%s)  and expected one %s(%s)' % (
                    call_name, key_name, key_value, type(key_value), value, type(value)))
            if value == key_value:
                return jsoner.dumps(res)
            return abort(500, u'bad value for %s: %s' % (key_name, value))
        
        
        def _generic_POST(key_name, expected_key_value, res, call_name):
            cprint(u'SERVER::_generic_POST:: POST.get :: %s(%s)' % (key_name, type(key_name)))
            
            content_type = request.headers.get('Content-Type')
            cprint(f'SERVER::_generic_POST:: Content-Type={content_type}')
            
            # read POST data
            d = request.get_json()
            cprint(f'SERVER::_generic_POST:: json={d}')
            
            if content_type == 'application/json':
                cprint(f'SERVER::_generic_POST:: json={request.get_json()}')
                value = request.get_json().get(key_name)
                value = bytes_to_unicode(value)
                return _generic_call(key_name, expected_key_value, res, call_name, value)
            
            cprint(f'SERVER::_generic_POST:: request.data={request.data} {type(request.data)}')
            raw_data = request.data
            cprint(f'SERVER::_generic_POST:: raw_data={raw_data} {type(raw_data)}')
            
            value = jsoner.loads(raw_data)
            value = value.get(key_name)
            value = bytes_to_unicode(value)
            return _generic_call(key_name, expected_key_value, res, call_name, value)
        
        
        def _generic_GET(key_name, key_value, res, call_name):
            # cprint('SERVER:: _generic_GET:: %s' % request.GET.__dict__)
            value = get_from_GET(request, key_name)  # request.GET.get(key_name)
            value = bytes_to_unicode(value)
            return _generic_call(key_name, key_value, res, call_name, value)
        
        
        def _generic_PUT(key_name, expected_key_value, res, call_name):
            try:
                cprint(f'SERVER:: _generic_PUT:: key_name={key_name} expected_key_value={expected_key_value} res={res} call_name={call_name}')
                cprint(f'SERVER:: _generic_PUT:: request={request}')
                content_type = request.headers.get('Content-Type')
                cprint(f'SERVER:: _generic_PUT:: Content-Type={content_type}')
                
                if content_type == 'application/json':
                    cprint(f'SERVER:: _generic_PUT:: json={request.get_json()}')
                    value = request.get_json().get(key_name)
                    value = bytes_to_unicode(value)
                    return _generic_call(key_name, expected_key_value, res, call_name, value)
                
                # application/octet-stream ?
                cprint(f'SERVER:: _generic_PUT:: request.data={request.data} {type(request.data)}')
                raw_data = request.data
                cprint(f'SERVER:: _generic_PUT:: raw_data={raw_data} {type(raw_data)}')
                
                value = jsoner.loads(raw_data)
                value = value.get(key_name)
                value = bytes_to_unicode(value)
                return _generic_call(key_name, expected_key_value, res, call_name, value)
            except Exception:
                cprint(f'SERVER:: _generic_PUT:: exception: {traceback.format_exc()}')
                raise
        
        
        ##############################
        ##### ARG/ASCII     RET/ASCII
        ##############################
        @http_export(u'/get_ret_ascii_arg_ascii')
        def f_get():
            return _generic_GET(ARG_ASCII_KEY, ARG_ASCII_VALUE, RES_ASCII, u'get_ret_ascii_arg_ascii')
        
        
        @http_export(u'/post_ret_ascii_arg_ascii', methods=['POST'])
        def f_post():
            return _generic_POST(ARG_ASCII_KEY, ARG_ASCII_VALUE, RES_ASCII, u'post_ret_ascii_arg_ascii')
        
        
        @http_export(u'/put_ret_ascii_arg_ascii', methods=['PUT'])
        def f_put():
            return _generic_PUT(ARG_ASCII_KEY, ARG_ASCII_VALUE, RES_ASCII, u'put_ret_ascii_arg_ascii')
        
        
        ############################
        ##### ARG/ASCII     RET/UTF8
        ############################
        @http_export(u'/get_ret_utf8_arg_ascii')
        def f_get_ret_utf8_arg_ascii():
            return _generic_GET(ARG_ASCII_KEY, ARG_ASCII_VALUE, RES_UTF8, u'get_ret_utf8_arg_ascii')
            # response.content_type = u'application/json'
            # arg = request.GET.get(ARG_ASCII_KEY)
            # if arg == ARG_ASCII_VALUE:
            #     return jsoner.dumps(RES_UTF8)
            # return abort(500, u'bad value for arg: %s' % arg)
        
        
        @http_export(u'/post_ret_utf8_arg_ascii', methods=['POST'])
        def f_post_ret_utf8_arg_ascii():
            return _generic_POST(ARG_ASCII_KEY, ARG_ASCII_VALUE, RES_UTF8, u'get_ret_utf8_arg_ascii')
        
        
        @http_export(u'/put_ret_utf8_arg_ascii', methods=['PUT'])
        def f_put_ret_utf8_arg_ascii():
            return _generic_PUT(ARG_ASCII_KEY, ARG_ASCII_VALUE, RES_UTF8, u'put_ret_utf8_arg_ascii')
        
        
        ############################
        ##### Value/UTF8     RET/UTF8
        ############################
        
        @http_export(u'/get_ret_utf8_value_utf8')
        def f_get_ret_utf8_value_utf8():
            return _generic_GET(VALUE_ONLY_UTF8_KEY, VALUE_ONLY_UTF8_VALUE, RES_UTF8, u'get_ret_utf8_value_utf8')
        
        
        @http_export(u'/post_ret_utf8_value_utf8', methods=['POST'])
        def f_post_ret_utf8_value_utf8():
            return _generic_POST(VALUE_ONLY_UTF8_KEY, VALUE_ONLY_UTF8_VALUE, RES_UTF8, u'post_ret_utf8_value_utf8')
        
        
        @http_export(u'/put_ret_utf8_value_utf8', methods=['PUT'])
        def f_put_utf8_ret_utf8_value_utf8():
            return _generic_PUT(VALUE_ONLY_UTF8_KEY, VALUE_ONLY_UTF8_VALUE, RES_UTF8, u'put_ret_utf8_value_utf8')
        
        
        ############################
        ##### ARG+value/UTF8     RET/UTF8
        ############################
        
        # @http_export(u'/get_ret_utf8_arg_utf8')
        @http_export(u'/get_ret_utf8_arg_utf8')
        def f_get_ret_utf8_arg_utf8():
            return _generic_GET(ARG_UTF8_KEY, ARG_UTF8_VALUE, RES_UTF8, u'get_ret_utf8_arg_utf8')
        
        
        @http_export(u'/post_ret_utf8_arg_utf8', methods=['POST'])
        def f_post_ret_utf8_arg_utf8():
            return _generic_POST(ARG_UTF8_KEY, ARG_UTF8_VALUE, RES_UTF8, u'post_ret_utf8_arg_utf8')
        
        
        @http_export(u'/put_ret_utf8_arg_utf8', methods=['PUT'])
        def f_put_utf8_ret_utf8_arg_utf8():
            return _generic_PUT(ARG_UTF8_KEY, ARG_UTF8_VALUE, RES_UTF8, u'put_ret_utf8_arg_utf8')
        
        
        ############################
        ##### URI/ASCII   RET/UTF8
        ############################
        @http_export('/get_uri_ascii_ret_utf8/<arg>')
        def f_get_uri_ascii_ret_utf8(arg):
            arg = bytes_to_unicode(arg)
            return _check_uri_call(ARG_ASCII_VALUE, RES_UTF8, '/get_uri_ascii_ret_utf8/<arg>', arg)
        
        
        ############################
        ##### URI/UTF8   RET/UTF8
        ############################
        @http_export(u'/get_uri_utf8_ret_utf8/<arg>')
        def f_get_uri_utf8_ret_utf8(arg):
            arg = bytes_to_unicode(arg)
            return _check_uri_call(ARG_UTF8_VALUE, RES_UTF8, u'/get_uri_utf8_ret_utf8/<arg>', arg)
        
        
        import threading
        t = threading.Thread(None, target=app.run, name='flask', kwargs={'debug':        True,
                                                                         'host':         'unix://%s' % SOCKET_PATH,
                                                                         'use_reloader': False,
                                                                         })
        t.daemon = True
        t.start()
        # app.run(debug=True, host='unix://%s' % SOCKET_PATH)
        # threader.create_and_launch(httpdaemon.run, name='Internal HTTP', args=('', 0, SOCKET_PATH,), essential=True, part='TEST')
        # threader.create_and_launch(httpdaemon.run, name='Internal HTTP', args=('127.0.0.1', 35888, '',), essential=True, part='TEST')
        time.sleep(5)
    
    
    def setUp(self):
        pass
    
    
    def _generic_GET_URI_test(self, uri, arg_value, expected_res):
        uri = u'%s/%s' % (uri, arg_value)
        cprint(u'[CLIENT] ***** GET  LOCAL  %s' % uri)
        rc, data = get_local(uri, SOCKET_PATH, method='GET')
        cprint(u'  R: rc=%s   data=%s' % (rc, data))
        self.assertEqual(200, rc)
        self.assertEqual(bytes, type(data))
        data_j = jsoner.loads(data)
        cprint(u'[CLIENT]   R: r=%s' % (data_j))
        self.assertEqual(data_j, expected_res)
        
        cprint(u'***** GET  JSON   %s' % uri)
        r = get_json(uri, SOCKET_PATH, method='GET')
        cprint(u'[CLIENT]   R: r=%s' % (r))
        self.assertEqual(r, expected_res)
    
    
    def _generic_GET_test(self, uri, params, expected_res):
        cprint('[CLIENT] ***** GET  LOCAL  %s' % uri)
        rc, data = get_local(uri, SOCKET_PATH, params=params, method='GET')
        cprint('[CLIENT]   R: rc=%s   data=%s' % (rc, data))
        self.assertEqual(200, rc)
        self.assertEqual(bytes, type(data))
        data_j = jsoner.loads(data)
        cprint('[CLIENT]   R: r=%s' % (data_j))
        self.assertEqual(data_j, expected_res)
        
        cprint('[CLIENT] ***** GET  JSON   %s' % uri)
        r = get_json(uri, SOCKET_PATH, params=params, method='GET')
        cprint('[CLIENT]   R: r=%s' % (r))
        self.assertEqual(r, expected_res)
    
    
    def _generic_POST_test(self, uri, params, expected_res):
        cprint('[CLIENT] ***** POST  LOCAL  %s' % uri)
        
        unix_socket = requests.compat.quote_plus(SOCKET_PATH)
        url = f'http+unix://{unix_socket}{uri}'
        cprint(f'[CLIENT] ***** POST  LOCAL  {url}  (ARGS={params})')
        
        response = requests.post(url, json=params, headers={'Content-Type': 'application/json'})  # PUT == data
        rc = response.status_code
        data = response.content
        
        #rc, data = get_local(uri, SOCKET_PATH, params=params, method='POST')
        cprint('[CLIENT] ***** POST   R: rc=%s   data=%s' % (rc, data))
        self.assertEqual(200, rc)
        self.assertEqual(bytes, type(data))
        data_j = jsoner.loads(data)
        cprint('[CLIENT] ***** POST   R: r=%s' % (data_j))
        self.assertEqual(data_j, expected_res)
        
        #cprint('[CLIENT] ***** POST  JSON  %s' % uri)
        #r = post_opsbro_json(uri, params)
        #cprint('[CLIENT] ***** POST  R: r=%s' % (r))
        #self.assertEqual(r, expected_res)
    
    
    def _generic_PUT_test(self, uri, params, expected_res):
        cprint('[CLIENT] ***** PUT  LOCAL  %s' % uri)
        # rc, data = get_local(uri, SOCKET_PATH, params=jsoner.dumps(params), method='PUT')
        unix_socket = requests.compat.quote_plus(SOCKET_PATH)
        url = f'http+unix://{unix_socket}{uri}'
        cprint(f'[CLIENT] ***** PUT  LOCAL  {url}  (ARGS={params})')
        response = requests.put(url, json=params, headers={'Content-Type': 'application/json'})  # PUT == data
        rc = response.status_code
        data = response.content
        
        cprint('[CLIENT]   R: rc=%s   data=%s' % (rc, data))
        self.assertEqual(200, rc)
        self.assertEqual(bytes, type(data))
        data_j = jsoner.loads(data)
        cprint('[CLIENT]   R: r=%s' % (data_j))
        self.assertEqual(data_j, expected_res)
        
        #cprint('[CLIENT] ***** PUT  JSON  %s' % uri)
        #r = put_opsbro_json(uri, jsoner.dumps(params))
        #cprint('[CLIENT]   R: r=%s' % (r))
        #self.assertEqual(r, expected_res)
    
    
    #### RET/ASCII   ARG/ASCII
    def test_unixclient_GET_ret_ascii_arg_ascii(self):
        self._generic_GET_test(u'/get_ret_ascii_arg_ascii', ARG_ASCII, RES_ASCII)
    
    
    def test_unixclient_POST_ret_ascii_arg_ascii(self):
        self._generic_POST_test(u'/post_ret_ascii_arg_ascii', ARG_ASCII, RES_ASCII)
        return
    
    
    def test_unixclient_PUT_ret_ascii_arg_ascii(self):
        self._generic_PUT_test(u'/put_ret_ascii_arg_ascii', ARG_ASCII, RES_ASCII)
    
    
    #### RET/UTF8   VALUE/UTF8
    def test_unixclient_GET_simple_ret_utf8_value_utf8(self):
        self._generic_GET_test(u'/get_ret_utf8_value_utf8', VALUE_ONLY_UTF8, RES_UTF8)
    
    
    def test_unixclient_POST_simple_ret_utf8_value_utf8(self):
        self._generic_POST_test(u'/post_ret_utf8_value_utf8', VALUE_ONLY_UTF8, RES_UTF8)
    
    
    def test_unixclient_PUT_simple_ret_utf8_value_utf8(self):
        self._generic_PUT_test(u'/put_ret_utf8_value_utf8', VALUE_ONLY_UTF8, RES_UTF8)
    
    
    #### RET/UTF8   ARG/UTF8
    def test_unixclient_GET_simple_ret_utf8_arg_utf8(self):
        self._generic_GET_test(u'/get_ret_utf8_arg_utf8', ARG_UTF8, RES_UTF8)
    
    
    def test_unixclient_POST_simple_ret_utf8_arg_utf8(self):
        self._generic_POST_test(u'/post_ret_utf8_arg_utf8', ARG_UTF8, RES_UTF8)
    
    
    def test_unixclient_PUT_simple_ret_utf8_arg_utf8(self):
        self._generic_PUT_test(u'/put_ret_utf8_arg_utf8', ARG_UTF8, RES_UTF8)
    
    
    #### URI/ASCII   RET/UTF8
    def test_unixclient_GET_URI_ret_utf8_uri_ascii(self):
        self._generic_GET_URI_test(u'/get_uri_ascii_ret_utf8', ARG_ASCII_VALUE, RES_UTF8)
    
    
    #### URI/UTF8   RET/UTF8
    def test_unixclient_GET_URI_ret_utf8_uri_utf8(self):
        self._generic_GET_URI_test(u'/get_uri_utf8_ret_utf8', ARG_UTF8_VALUE, RES_UTF8)


if __name__ == '__main__':
    unittest.main()
