import os
import shutil
import glob
import socket
import hashlib
import uuid as libuuid

from opsbro.log import logger
from opsbro.hostingdrivermanager import get_hostingdrivermgr


def make_dir(path):
    if not os.path.isdir(path):
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


# The public IP can be a bit complex, as maybe the local host do not even have it in it's
# network interface: EC2 and scaleway are example of public ip -> NAT -> private one and
# the linux do not even know it
def get_public_address():
    hosttingctxmgr = get_hostingdrivermgr()
    
    addr = hosttingctxmgr.get_public_address()
    return addr


# Try to GET (fixed) uuid, but only if a constant one is here
# * linux: get hardware uuid from dmi (but not in docker case)
# * aws:   get instance uuid from url (TODO)
# * windows: TODO
def get_server_const_uuid():
    # First DMI, if there is a UUID, use it
    # BUT not if docker one (have access to DMI but it's a container, so not unique)
    product_uuid_p = '/sys/class/dmi/id/product_uuid'
    if os.path.exists(product_uuid_p) and not os.path.exists('/.dockerenv'):
        with open(product_uuid_p, 'r') as f:
            buf = f.read()
        logger.info('[SERVER-UUID] using the DMI (bios) uuid as server unique UUID: %s' % buf.lower())
        return hashlib.sha1(buf.lower()).hexdigest()
    # TODO:
    # aws
    # windows
    # docker
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
