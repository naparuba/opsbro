# -*- coding: utf-8 -*-

import sys
import os
import shutil
import glob
import socket
import hashlib
import time
import uuid as libuuid
import base64
import re

PY3 = sys.version_info >= (3,)
if PY3:
    basestring = str

from .log import LoggerFactory, DEFAULT_LOG_PART
from .type_hint import TYPE_CHECKING

if TYPE_CHECKING:
    from .type_hint import Optional, Tuple, List, Any, Dict

logger = LoggerFactory.create_logger(DEFAULT_LOG_PART)


# FROM : https://stackoverflow.com/questions/14383937/check-printable-for-unicode
# match characters from ¿ to the end of the JSON-encodable range
IS_PRINTABLE_EXCLUDE_RANGE = re.compile(r'[\u00bf-\uffff]')

def b64_into_unicode(b64_string):
    return bytes_to_unicode(base64.b64decode(b64_string))


def b64_into_bytes(b64_string):
    return base64.b64decode(b64_string)  # base 64 already give bytes


def string_to_b64unicode(s):
    return bytes_to_unicode(base64.b64encode(s))


def epoch_to_human_string(t_epoch):
    return time.strftime("%Y-%b-%d %H:%M:%S", time.localtime(t_epoch))


def is_character_printable(c):
    # type: (str) -> bool
    if PY3:
        return c.isprintable()
    # python 2: need to go with a regexp
    return not bool(IS_PRINTABLE_EXCLUDE_RANGE.search(c))
        

# Make a directory with recursive creation if need
# Can send IOError if a file already exists with the name
def make_dir(path):
    # type: (str) -> None
    
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


def exec_command(cmd):
    # type: (str) -> Tuple[int, str, str]
    
    import subprocess
    # If we have a list, we should not call with a shell
    shell = False if isinstance(cmd, list) else True
    # close_fds: I used to set True on unix (False on Windows because it do not manage it)
    # but it's just tooooooo cpu consuming, calling 65K time close()
    # so... nop
    close_fds = False
    # There is no setsid function on windows
    preexec_fn = getattr(os, 'setsid', None)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=close_fds, preexec_fn=preexec_fn, shell=shell)
    stdout, stderr = p.communicate()
    stdout = bytes_to_unicode(stdout)
    stderr = bytes_to_unicode(stderr)
    return p.returncode, stdout, stderr


def my_sort(lst, cmp_f):
    # type: (List, Any) -> List
    if not PY3:
        lst = sorted(lst, cmp=cmp_f)
    else:
        from functools import cmp_to_key
        lst = sorted(lst, key=cmp_to_key(cmp_f))
    return lst


def my_cmp(a, b):
    # type: (Any, Any) -> bool
    if PY3:
        return ((a > b) - (a < b))
    return cmp(a, b)


def copy_dir(source_item, destination_item):
    # type: (str, str) -> None
    if os.path.isdir(source_item):
        make_dir(destination_item)
        sub_items = glob.glob(source_item + '/*')
        for sub_item in sub_items:
            copy_dir(sub_item, destination_item + '/' + sub_item.split('/')[-1])
    else:
        shutil.copy(source_item, destination_item)


def to_best_int_float(val):
    # type: (Optional[int, float]) -> Optional[int, float]
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
    # type: (Dict) -> Dict
    r = {}
    for (k, v) in d.items():
        r[k.lower()] = v
    return r


# Try to GET (fixed) uuid, but only if a constant one is here
# * linux: get hardware uuid from dmi (but not in docker case)
# * aws:   get instance uuid from url (TODO)
# * windows: TODO
def get_server_const_uuid():
    # type: () -> str
    from .hostingdrivermanager import get_hostingdrivermgr
    # Ask the hosting driver if a unique uuid is available
    # linux:     # First DMI, if there is a UUID, use it
    # BUT not if docker one (have access to DMI but it's a container, so not unique)
    # ec2: can use uuid from meta_data
    hosttingdrvmgr = get_hostingdrivermgr()
    unique_uuid = hosttingdrvmgr.get_unique_uuid()
    if unique_uuid:
        return get_sha1_hash(unique_uuid.lower())
    return ''


def get_sha1_hash(s):
    # type: (str) -> str
    # NOTE: hashlib (in python3) take str, not unicode
    if isinstance(s, str):
        s = s.encode('utf8', 'ignore')
    return hashlib.sha1(s).hexdigest()


def get_uuid():
    # type: () -> str
    u = libuuid.uuid1()
    if PY3:
        return u.hex
    else:
        return u.get_hex()


# Bytes to unicode
def string_decode(s):
    return bytes_to_unicode(s)


# Bytes to unicode
def bytes_to_unicode(s):
    # type: (Optional[bytes, str]) -> str
    if isinstance(s, str) and not PY3:  # python3 already is unicode in str
        return s.decode('utf8', 'ignore')
    if PY3 and (isinstance(s, bytes) or isinstance(s, bytearray)):  # bytearray is bytes that can mutate
        return s.decode('utf8', 'ignore')
    return s


# Unicode to bytes
def string_encode(s):
    return unicode_to_bytes(s)


def unicode_to_bytes(s):
    # type: (Optional[bytes, str]) -> bytes
    if isinstance(s, str) and PY3:
        return s.encode('utf8', 'ignore')
    return s


# Try to guess uuid, but can be just a guess, so TRY to have a constant
# * openvz: take the local server ID + hostname as base
def guess_server_const_uuid():
    # type: () -> str
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
    return hashlib.sha1(unicode_to_bytes(get_uuid())).hexdigest()


# recursivly change a dict with pure bytes
def byteify(input):
    # type: (Any) -> Any
    if isinstance(input, dict):
        return dict([(byteify(key), byteify(value)) for key, value in input.items()])
    elif isinstance(input, list):
        return [byteify(element) for element in input]
    elif isinstance(input, str) and not PY3:  # python3 already is unicode in str
        return input.decode('utf8', 'ignore')
    else:
        return input


PAGESIZE = 0


def get_memory_consumption():
    # type: () -> int
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
    # type: () -> int
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


############# String diffs
def unified_diff(from_lines, to_lines, pth=''):
    # type: (Optional[str, List[str]],Optional[str, List[str]], str) -> List[str]
    # Lazyload this, they are huge libs
    import re
    import difflib
    from .characters import CHARACTERS
    
    if isinstance(from_lines, basestring):
        from_lines = from_lines.splitlines()
    
    if isinstance(to_lines, basestring):
        to_lines = to_lines.splitlines()
    
    pat_diff = re.compile(r'@@ (.[0-9]+\,[0-9]+) (.[0-9]+,[0-9]+) @@')
    
    diff_lines = []
    
    lines = list(difflib.unified_diff(from_lines, to_lines, n=1))
    
    from_lnum = 0
    to_lnum = 0
    
    first_diff = True
    
    for line in lines:
        if line.startswith(u'--') or line.startswith(u'++'):
            continue
        
        m = pat_diff.match(line)
        if m:
            left = m.group(1)
            right = m.group(2)
            lstart = left.split(',')[0][1:]
            rstart = right.split(',')[0][1:]
            # We do not want to add a \n on the very first block
            prefix = '' if first_diff else '\n'
            first_diff = False
            diff_lines.append(u"%s%s%s Change %s (line, change size): %s %s %s" % (prefix, CHARACTERS.corner_top_left, CHARACTERS.hbar * 10, pth, left, CHARACTERS.arrow_left, right))
            to_lnum = int(lstart)
            from_lnum = int(rstart)
            continue
        
        code = line[0]
        
        lnum = from_lnum
        if code == '-':
            lnum = to_lnum
        diff_lines.append(u"%s%.4d: %s" % (code, lnum, line[1:]))
        
        if code == '-':
            to_lnum += 1
        elif code == '+':
            from_lnum += 1
        else:
            to_lnum += 1
            from_lnum += 1
    
    return diff_lines
