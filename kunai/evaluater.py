import re
import ast
import _ast
import operator as op
import json
import base64
import inspect
import types
import itertools

from kunai.collectormanager import collectormgr
from kunai.log import LoggerFactory
from kunai.httpdaemon import route, response, request

# Global logger for this part
logger = LoggerFactory.create_logger('evaluater')

# supported operators
operators = {
    ast.Add   : op.add,  # A + B
    ast.Sub   : op.sub,  # A - B
    ast.Mult  : op.mul,  # A * B
    ast.Div   : op.truediv,  # A / B
    ast.Pow   : op.pow,  # ???
    ast.BitXor: op.xor,  # ???
    ast.USub  : op.neg,  # ???
    ast.Eq    : op.eq,  # A == B
    ast.NotEq : op.ne,  # A != B
    ast.Gt    : op.gt,  # A > B
    ast.Lt    : op.lt,  # A < B
    ast.GtE   : op.ge,  # A >= B
    ast.LtE   : op.le,  # A <= B
    ast.Mod   : op.mod,  # A % B
    ast.Or    : op.or_, _ast.Or: op.or_,  # A or B
    ast.And   : op.and_, _ast.And: op.and_,  # A and B
    ast.BitOr : op.or_,  # A | B
    ast.BitAnd: op.and_,  # A & B
    ast.Not   : op.not_, _ast.Not: op.not_,  # not A
    ast.In    : op.contains,  # A in L
    # NOTMANAGE ast.Subscript: op.getitem, _ast.Subscript: op.getitem,  # d[k]
}

functions = {
    'abs': abs,
}


def export_evaluater_function(f):
    # Export the function to the allowed functions
    fname = f.__name__
    functions[fname] = f
    logger.debug('Evaluater: exporting function %s' % fname)
    return f


names = {'True': True, 'False': False}


class Evaluater(object):
    def __init__(self):
        self.cfg_data = {}
        self.pat = re.compile('{{.*?}}')
    
    
    def load(self, cfg_data):
        self.cfg_data = cfg_data
    
    
    def compile(self, expr, check=None):
        # first manage {} thing and look at them
        all_parts = self.pat.findall(expr)
        
        changes = []
        
        for p in all_parts:
            p = p[2:-2]  # remove {{ and }}
            
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
            raise ValueError('Some parts between {} cannot be changed')
        
        for (p, v) in changes:
            expr = expr.replace('{{%s}}' % p, str(v))
        
        return expr
    
    
    def eval_expr(self, expr, check=None):
        logger.debug('EVAL: expression: %s' % expr)
        expr = self.compile(expr, check=check)
        logger.debug('EVAL: exp changed: %s' % expr)
        # final tree
        tree = ast.parse(expr, mode='eval').body
        try:
            r = self.eval_(tree)
        except Exception, exp:
            logger.debug('EVAL: fail to eval expr: %s : %s' % (expr, exp))
            raise
        logger.debug('EVAL: result: %s' % r)
        return r
    
    
    def eval_(self, node):
        logger.debug('eval_ node: %s => type=%s' % (node, type(node)))
        if isinstance(node, ast.Num):  # <number>
            return node.n
        elif isinstance(node, ast.Str):  # <string>
            return node.s
        elif isinstance(node, ast.List):  # <list>
            return [self.eval_(e) for e in node.elts]
        elif isinstance(node, ast.Dict):  # <dict>
            _keys = [self.eval_(e) for e in node.keys]
            _values = [self.eval_(e) for e in node.values]
            _dict = dict(itertools.izip(_keys, _values))  # zip it into a new dict
            return _dict
        elif isinstance(node, ast.BinOp):  # <left> <operator> <right>
            return operators[type(node.op)](self.eval_(node.left), self.eval_(node.right))
        elif isinstance(node, _ast.BoolOp):  # <elt1> OP <elt2>   TOD: manage more than 2 params
            if len(node.values) != 2:
                raise Exception('Cannot manage and/or operators woth more than 2 parts currently.')
            return operators[type(node.op)](self.eval_(node.values[0]), self.eval_(node.values[1]))
        elif isinstance(node, ast.Compare):  # <left> <operator> <right>
            left = self.eval_(node.left)
            right = self.eval_(node.comparators[0])
            _op = operators[type(node.ops[0])]
            reversed_operator = [op.contains]  # some operators are in the right,left order!!
            if _op not in reversed_operator:
                return _op(left, right)
            else:  # reverse order
                return _op(right, left)
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
                logger.error('Eval UNMANAGED (ast.aTTribute) CALL: %s %s %s is refused' % (node.func, node.func.__dict__, node.func.value.__dict__))
            
            else:
                logger.error('Eval UNMANAGED (othercall) CALL: %s %s %s is refused' % (node.func, node.func.__dict__, node.func.value.__dict__))
                raise TypeError(node)
            
            if f:
                v = f(*args)
                return v
        else:
            logger.error('Eval UNMANAGED node: %s %s and so is  refused' % (node, type(node)))
            raise TypeError(node)
    
    
    # Try to find the params for a macro in the foloowing objets, in that order:
    # * check
    # * service
    # * main configuration
    def _found_params(self, m, check):
        # only import it now because if not will do an import loop
        from kunai.monitoring import monitoringmgr
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
                if sname and sname in monitoringmgr.services:
                    service = monitoringmgr.services.get(sname)
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
