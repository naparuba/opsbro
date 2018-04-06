import os
import shutil
import glob
import socket
import hashlib
import time
import uuid as libuuid

from .log import logger
from .hostingdrivermanager import get_hostingdrivermgr


# Make a directory with recursive creation if need
# Can send IOError if a file already exists with the name
def make_dir(path):
    # Already exists as a directory
    # NOTICE: will always ends as the root dir will exists
    # note: '' if for windows, as I am not sure about the root directory
    if os.path.isdir(path) or path == '':
        return
    # Do not exists, but the path is already there by a file!
    if os.path.exists(path):
        raise IOError('Asking to create the directory %s but a file already exits there' % path)
    # assert that the parent directory does exists
    parent, dir_name = os.path.split(path)
    if dir_name == '':  # was ending by a /, skip this loop, dir_name is useless
        return make_dir(parent)
    # assert that the parent does exists
    make_dir(parent)
    # so now we can create the son
    os.mkdir(path)


def copy_dir(source_item, destination_item):
    if os.path.isdir(source_item):
        make_dir(destination_item)
        sub_items = glob.glob(source_item + '/*')
        for sub_item in sub_items:
            copy_dir(sub_item, destination_item + '/' + sub_item.split('/')[-1])
    else:
        shutil.copy(source_item, destination_item)


def to_best_int_float(val):
    try:
        i = int(float(val))
        f = float(val)
    except ValueError:
        return None
        # If the f is a .0 value,
        # best match is int
    if i == f:
        return i
    return f


# get a dict but with key as lower
def lower_dict(d):
    r = {}
    for (k, v) in d.iteritems():
        r[k.lower()] = v
    return r


# Try to GET (fixed) uuid, but only if a constant one is here
# * linux: get hardware uuid from dmi (but not in docker case)
# * aws:   get instance uuid from url (TODO)
# * windows: TODO
def get_server_const_uuid():
    # Ask the hosting driver if a unique uuid is available
    # linux:     # First DMI, if there is a UUID, use it
    # BUT not if docker one (have access to DMI but it's a container, so not unique)
    # ec2: can use uuid from meta_data
    hosttingdrvmgr = get_hostingdrivermgr()
    unique_uuid = hosttingdrvmgr.get_unique_uuid()
    if unique_uuid:
        return hashlib.sha1(unique_uuid.lower()).hexdigest()
    
    return ''


# Try to guess uuid, but can be just a guess, so TRY to have a constant
# * openvz: take the local server ID + hostname as base
def guess_server_const_uuid():
    # For OpenVZ: there is an ID that is unique but for a hardware host,
    # so to avoid have 2 different host with the same id, mix this id and the hostname
    openvz_info_p = '/proc/vz/veinfo'
    if os.path.exists(openvz_info_p):
        with open(openvz_info_p, 'r') as f:
            buf = f.read()
            # File:    ID    MORE-STUFF
            openvz_id = int(buf.strip().split(' ')[0])
            servr_uniq_id = '%s-%d' % (socket.gethostname().lower(), openvz_id)
            logger.info('[SERVER-UUID] OpenVZ: using the hostname & openvz local id as server unique UUID: %s' % servr_uniq_id)
            return hashlib.sha1(servr_uniq_id).hexdigest()
    # No merly fixed stuff? ok, pure randomness
    return hashlib.sha1(libuuid.uuid1().get_hex()).hexdigest()


# recursivly change a dict with pure bytes
def byteify(input):
    if isinstance(input, dict):
        return dict([(byteify(key), byteify(value)) for key, value in input.iteritems()])
    elif isinstance(input, list):
        return [byteify(element) for element in input]
    elif isinstance(input, str):
        return input.decode('utf8', 'ignore')
    else:
        return input


PAGESIZE = 0


def get_memory_consumption():
    global PAGESIZE
    # TODO: manage windows
    if os.name == 'nt':
        return 0
    # not linux?
    if not os.path.exists('/proc/self/statm'):
        return 0
    if PAGESIZE == 0:
        PAGESIZE = os.sysconf('SC_PAGESIZE')
    return int(open('/proc/self/statm').read().split()[1]) * PAGESIZE


daemon_start = time.time()


def get_cpu_consumption():
    global daemon_start
    if os.name == 'nt':
        return 0
    # Some special unix maybe?
    try:
        from resource import getrusage, RUSAGE_SELF
    except ImportError:
        return 0
    now = time.time()
    # Maybe we did get back in time?
    if now < daemon_start:
        daemon_start = now
    diff = now - daemon_start
    if diff == 0:
        return 0
    rusage = getrusage(RUSAGE_SELF)
    current_cpu_time = rusage.ru_utime + rusage.ru_stime
    return 100 * current_cpu_time / diff
