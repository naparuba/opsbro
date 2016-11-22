import os
import re
import ast
import operator as op
import socket
import json
import base64
import time
import inspect
import types

try:
    import apt
except ImportError:
    apt = None

try:
    import yum
except ImportError:
    yum = None

from kunai.collectormanager import collectormgr
from kunai.log import logger
from kunai.misc.IPy import IP
from kunai.httpdaemon import route, response, request

# supported operators
operators = {
    ast.Add  : op.add, ast.Sub: op.sub, ast.Mult: op.mul,
    ast.Div  : op.truediv, ast.Pow: op.pow, ast.BitXor: op.xor,
    ast.USub : op.neg, ast.Eq: op.eq, ast.Gt: op.gt, ast.Lt: op.lt,
    ast.GtE  : op.ge, ast.LtE: op.le, ast.Mod: op.mod, ast.Or: op.or_,
    ast.BitOr: op.or_,
}

functions = {
    'abs': abs,
}


def export(f):
    def inner(*args, **kwargs):  # 1
        return f(*args, **kwargs)  # 2
    
    
    # Export the function to the allowed functions
    fname = f.__name__
    functions[fname] = f  # inner
    inner.linked = f
    logger.debug('Evaluater: exporting function %s' % fname)
    return f  # inner


@export
def file_exists(path):
    """file_exists(path) -> return True if a path exist on the system, False otherwise.
    * path: (string) path to check.
    
    Example: file_exists('/etc/mongodb.conf')
    """
    return os.path.exists(path)


@export
def ip_is_in_range(ip, range):
    """ip_is_in_range(ip, range) -> return True if the ip is in the ip range, False otherwise.
    * ip:     (string) ip (v4 or v6) to check
    * range:  (string) ip range that the ip must be in
    
    Example:  ip_is_in_range('172.16.0.30', '172.16.0.0/24')
    """

    ip_range = IP(range)
    return ip in ip_range


@export
def grep_file(string, path, regexp=False):
    """file_exists(path) -> return True if a string or a regexp match the content of a file, False otherwise.
    * string: (string)  string (or regexp expression) to check
    * path: (string) path of the file to look inside.
    * regexp: (boolean) is the string a regexp or not.
    
    Example: grep_file('centos', '/etc/redhat-release')
    """
    s = string
    p = path
    if not os.path.exists(p):
        return False
    try:
        f = open(p, 'r')
        lines = f.readlines()
    except Exception, exp:
        logger.debug('Trying to grep file %s but cannot open/read it: %s' % (p, exp))
        return False
    pat = None
    if regexp:
        try:
            pat = re.compile(s, re.I)
        except Exception, exp:
            logger.debug('Cannot compile regexp expression: %s')
        return False
    if regexp:
        for line in lines:
            if pat.search(line):
                return True
    else:
        s = s.lower()
        for line in lines:
            if s in line.lower():
                return True
    return False


deb_cache = None
deb_cache_update_time = 0
DEB_CACHE_MAX_AGE = 60  # if we cannot look at dpkg data age, allow a max cache of 60s to get a new apt update from disk
DPKG_CACHE_PATH = '/var/cache/apt/pkgcache.bin'
dpkg_cache_last_modification_epoch = 0.0

yumbase = None


@export
def has_package(package):
    """has_package(package) -> return True if the package is installed on the system, False otherwise.
    * package: (string) name of the package to check for.
    
    Example: has_package('postfix')
    """
    global deb_cache, deb_cache_update_time, dpkg_cache_last_modification_epoch
    global yumbase
    
    if apt:
        t0 = time.time()
        if not deb_cache:
            deb_cache = apt.Cache()
            deb_cache_update_time = int(time.time())
        else:  # ok already existing, look if we should update it
            # because if there was a package installed, it's no more in cache
            need_reload = False
            if os.path.exists(DPKG_CACHE_PATH):
                last_change = os.stat(DPKG_CACHE_PATH).st_mtime
                if last_change != dpkg_cache_last_modification_epoch:
                    need_reload = True
                    dpkg_cache_last_modification_epoch = last_change
            else:  # ok we cannot look at the dpkg file age, must limit by time
                # the cache is just a memory view, so if too old, need to udpate it
                if deb_cache_update_time < time.time() - DEB_CACHE_MAX_AGE:
                    need_reload = True
            if need_reload:
                deb_cache.open(None)
                deb_cache_update_time = int(time.time())
        b = (package in deb_cache and deb_cache[package].is_installed)
        logger.debug('TIME TO QUERY APT: %.3f' % (time.time() - t0), part='evaluator')
        return b
    if yum:
        if not yumbase:
            yumbase = yum.YumBase()
            yumbase.conf.cache = 1
        return package in (pkg.name for pkg in yumbase.rpmdb.returnPackages())


@export
def check_tcp(host, port, timeout=10):
    """check_tcp(host, port, timeout=10) -> return True if the TCP connection can be established, False otherwise.
    * host: (string) ip/fqdn of the host to connect to.
    * port: (integer) TCP port to connect to
    * timeout [optionnal] (integer) timeout to use for the connection test.

    Example: check_tcp('www.google.com', 80)
    """
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        sock.close()
        return True
    except socket.error:
        sock.close()
        return False


@export
def get_os():
    """get_os() -> return a string about the os.

    Example: get_os()
    
    Returns:  linux
    """

    import platform
    return platform.system().lower()


names = {'True': True, 'False': False}


class Evaluater(object):
    def __init__(self):
        self.cfg_data = {}
        self.services = {}
    
    
    def load(self, cfg_data, services):
        self.cfg_data = cfg_data
        self.services = services
    
    
    def compile(self, expr, check=None):
        # first manage {} thing and look at them
        all_parts = re.findall('{.*?}', expr)
        
        changes = []
        
        for p in all_parts:
            p = p[1:-1]
            
            if p.startswith('collector.'):
                s = p[len('collector.'):]
                v = collectormgr.get_data(s)
                logger.debug('Ask', s, 'got', v)
                changes.append((p, v))
            elif p.startswith('configuration.'):
                s = p[len('configuration.'):]
                v = self._found_params(s, check)
                changes.append((p, v))
        
        if not len(changes) == len(all_parts):
            raise ValueError('Some parts cannot be changed')
        
        for (p, v) in changes:
            expr = expr.replace('{%s}' % p, str(v))
        
        return expr
    
    
    def eval_expr(self, expr, check=None):
        logger.debug('EVAL: expression: %s' % expr, part='evaluator')
        expr = self.compile(expr, check=check)
        logger.debug('EVAL: exp changed: %s' % expr, part='evaluator')
        # final tree
        tree = ast.parse(expr, mode='eval').body
        r = self.eval_(tree)
        logger.debug('EVAL: result: %s' % r, part='evaluator')
        return r
    
    
    def eval_(self, node):
        if isinstance(node, ast.Num):  # <number>
            return node.n
        elif isinstance(node, ast.Str):  # <string>
            return node.s
        elif isinstance(node, ast.BinOp):  # <left> <operator> <right>
            return operators[type(node.op)](self.eval_(node.left), self.eval_(node.right))
        elif isinstance(node, ast.Compare):  # <left> <operator> <right>
            left = self.eval_(node.left)
            right = self.eval_(node.comparators[0])
            return operators[type(node.ops[0])](left, right)
        elif isinstance(node, ast.UnaryOp):  # <operator> <operand> e.g., -1
            return operators[type(node.op)](self.eval_(node.operand))
        elif isinstance(node, ast.Name):  # name? try to look at it
            key = node.id
            v = names.get(key, None)
            return v
        elif isinstance(node, ast.Call):  # call? dangerous, must be registered :)
            args = [self.eval_(arg) for arg in node.args]
            f = None
            # print 'attr?', isinstance(node.func, ast.Attribute)
            # print 'name?', isinstance(node.func, ast.Name)
            if isinstance(node.func, ast.Name):
                fname = node.func.id
                f = functions.get(fname, None)
            elif isinstance(node.func, ast.Attribute):
                print 'UNMANAGED CALL', node.func, node.func.__dict__, node.func.value.__dict__
            
            else:
                print node.__dict__
                raise TypeError(node)
            
            if f:
                v = f(*args)
                return v
        else:
            raise TypeError(node)
    
    
    # Try to find the params for a macro in the foloowing objets, in that order:
    # * check
    # * service
    # * main configuration
    def _found_params(self, m, check):
        parts = [m]
        # if we got a |, we got a default value somewhere
        if '|' in m:
            parts = m.split('|', 1)
        change_to = ''
        
        for p in parts:
            elts = [p]
            if '.' in p:
                elts = p.split('.')
            elts = [e.strip() for e in elts]
            
            # we will try to grok into our cfg_data for the k1.k2.k3 =>
            # self.cfg_data[k1][k2][k3] entry if exists
            d = None
            founded = False
            
            # if we got a check, we can look into it, and maybe the
            # linked service
            if check:
                # We will look into the check>service>global order
                # but skip serviec if it's not related with the check
                sname = check.get('service', '')
                find_into = [check, self.cfg_data]
                if sname and sname in self.services:
                    service = self.services.get(sname)
                    find_into = [check, service, self.cfg_data]
            # if not, just the global configuration will be ok :)
            else:
                find_into = [self.cfg_data]
            
            for tgt in find_into:
                (lfounded, ld) = self._found_params_inside(elts, tgt)
                if not lfounded:
                    continue
                if lfounded:
                    founded = True
                    d = ld
                    break
            if not founded:
                continue
            change_to = str(d)
            break
        return change_to
    
    
    # Try to found a elts= k1.k2.k3 => d[k1][k2][k3] entry
    # if exists
    def _found_params_inside(self, elts, d):
        founded = False
        for e in elts:
            if e not in d:
                founded = False
                break
            d = d[e]
            founded = True
        return (founded, d)
    
    
    # main method to export http interface. Must be in a method that got
    # a self entry
    def export_http(self):
        
        @route('/agent/evaluator/list')
        def get_exports():
            response.content_type = 'application/json'
            res = []
            fnames = functions.keys()
            fnames.sort()
            for fname in fnames:
                print "FNAME", fname
                f = functions[fname]
                print "FUNCTION", f
                _doc = getattr(f, '__doc__')
                # now get prototype

                # only possible if functions have
                if isinstance(f, types.FunctionType):
                    argspec = inspect.getargspec(f)
                    print "ARGSPECS", argspec
                    argnames = argspec.args
                    print "ARGNAMES", argnames
                    args = []
                    for arg in argnames:
                        args.append([arg, '__NO_DEFAULT__'])
                    # varargs = argspec.varargs
                    # keywords = argspec.keywords
                    # unzip default parameters
                    defaults = argspec.defaults
                    if defaults:
                        default_args = zip(argspec.args[-len(argspec.defaults):], argspec.defaults)
                        for (argname, defavalue) in default_args:
                            for c in args:
                                if c[0] == argname:
                                    c[1] = str(defavalue)
                else:
                    args = None
                
                prototype = args
                res.append({'name': fname, 'doc': _doc, 'prototype': prototype})
            return json.dumps(res)
        
        
        @route('/agent/evaluator/eval', method='POST')
        def agent_eval_check():
            response.content_type = 'application/json'
            expr64 = request.POST.get('expr')
            expr = base64.b64decode(expr64)
            print "/agent/evaluator/eval is called for query %s" % expr
            v = evaluater.eval_expr(expr)
            print "/agent/evaluator/eval result is %s" % v
            return json.dumps(v)


evaluater = Evaluater()
