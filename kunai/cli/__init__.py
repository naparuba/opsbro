import os
import json
import requests
from kunai.log import cprint, logger
from kunai.unixclient import get_json, get_local, request_errors

# Will be populated by the shinken CLI command
CONFIG = None


def get_local_socket():
    return CONFIG.get('socket', '/var/lib/kunai/kunai.sock')


if os.name != 'nt':
    def get_kunai_json(uri):
        local_socket = get_local_socket()
        return get_json(uri, local_socket)


    def get_kunai_local(uri):
        local_socket = get_local_socket()
        return get_local(uri, local_socket)


    def post_kunai_json(uri, data):
        local_socket = get_local_socket()
        return get_json(uri, local_socket, params=data, method='POST')


    def put_kunai_json(uri, data):
        local_socket = get_local_socket()
        return get_json(uri, local_socket, params=data, method='PUT')


else:
    def get_kunai_json(uri):
        r = requests.get('http://127.0.0.1:6770%s' % uri)
        obj = json.loads(r.text)
        return obj


    def get_kunai_local(uri):
        r = requests.get('http://127.0.0.1:6770%s' % uri)
        status = r.status_code
        text = r.text
        return (status, text)


def print_info_title(title):
    # t = title.ljust(15)
    # s = '=================== %s ' % t
    # s += '='*(50 - len(s))
    # cprint(s)
    cprint('========== [%s]:' % title)


def print_2tab(e, capitalize=True, col_size=20):
    for (k, v) in e:
        label = k
        if capitalize:
            label = label.capitalize()
        s = '%s: ' % label
        s = s.ljust(col_size)
        cprint(s, end='', color='blue')
        # If it's a dict, we got additiionnal data like color or type
        if isinstance(v, dict):
            color = v.get('color', 'green')
            _type = v.get('type', 'std')
            value = v.get('value')
            cprint(value, color=color)
        else:
            cprint(v, color='green')
