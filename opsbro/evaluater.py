import re
import ast
import _ast
import operator as op
import json
import base64
import inspect
import types
import itertools

from opsbro.collectormanager import collectormgr
from opsbro.log import LoggerFactory
from opsbro.httpdaemon import http_export, response, request

# Global logger for this part
logger = LoggerFactory.create_logger('evaluater')

# supported operators
operators = {
    ast.Add      : op.add,  # A + B
    ast.Sub      : op.sub,  # A - B
    ast.Mult     : op.mul,  # A * B
    ast.Div      : op.truediv,  # A / B
    ast.Pow      : op.pow,  # ???
    ast.BitXor   : op.xor,  # ???
    ast.USub     : op.neg,  # ???
    ast.Eq       : op.eq,  # A == B
    ast.NotEq    : op.ne,  # A != B
    ast.Gt       : op.gt,  # A > B
    ast.Lt       : op.lt,  # A < B
    ast.GtE      : op.ge,  # A >= B
    ast.LtE      : op.le,  # A <= B
    ast.Mod      : op.mod,  # A % B
    ast.Or       : op.or_, _ast.Or: op.or_,  # A or B
    ast.And      : op.and_, _ast.And: op.and_,  # A and B
    ast.BitOr    : op.or_,  # A | B
    ast.BitAnd   : op.and_,  # A & B
    ast.Not      : op.not_, _ast.Not: op.not_,  # not A
    ast.In       : op.contains,  # A in L
    ast.Subscript: op.getitem, _ast.Subscript: op.getitem,  # d[k]
    ast.Attribute: op.attrgetter, _ast.Attribute: op.attrgetter,  # d.XXXX()
}

functions = {
}

functions_to_groups = {
}


# This allow to have parameter for export_evaluater_function
# Python guys: decorators are a nightmare, impossible without google for simple task...
def parametrized(dec):
    def layer(*args, **kwargs):
        def repl(f):
            return dec(f, *args, **kwargs)
        
        
        return repl
    
    
    return layer


def _export_evaluater_function(f, function_group):
    # Export the function to the allowed functions
    fname = f.__name__
    functions[fname] = f
    functions_to_groups[fname] = function_group
    logger.debug('Evaluater: exporting function %s' % fname)
    return f


@parametrized
def export_evaluater_function(f, function_group):
    return _export_evaluater_function(f, function_group)


for f in (abs, min, max, sum, sorted, len, set):
    # NOTE: find why, but we need to call the not decorated function... cool...
    _export_evaluater_function(f, function_group='basic')

names = {'True': True, 'False': False}


class Evaluater(object):
    def __init__(self):
        self.cfg_data = {}
        self.pat = re.compile('{{.*?}}')
    
    
    def load(self, cfg_data):
        self.cfg_data = cfg_data
    
    
    def compile(self, expr, check=None, to_string=False, variables={}):
        # first manage {} thing and look at them
        all_parts = self.pat.findall(expr)
        
        changes = []
        
        for p in all_parts:
            orig_p = p  # save the original expression, with {{}} and default parts
            default_s = ''
            p = p[2:-2]  # remove {{ and }}
            # If there is a EXPR||DEFAULT we split in the part we need to grok, and the default
            if '||' in p:
                part1, part2 = p.split('||', 1)
                # get EXPR to get
                p = part1
                # and the default value to evaluate if need
                default_s = part2
            
            if p.startswith('collector.'):
                s = p[len('collector.'):]
                try:
                    v = collectormgr.get_data(s)
                except KeyError:  # ok cannot find it, try to switch to default if there is one
                    if default_s == '':
                        v = ''
                    else:  # ok try to compile it to get a real python object
                        v = self.compile(default_s, check=check, to_string=to_string)
                logger.debug('Ask', s, 'got', v)
                changes.append((orig_p, v))
            elif p.startswith('parameters.'):
                s = p[len('parameters.'):]
                v = self._found_params(s, check)
                changes.append((orig_p, v))
            elif p.startswith('variables.'):
                s = p[len('variables.'):]
                v = variables[s]
                changes.append((orig_p, v))
            else:
                raise Exception('The {{ }} expression: %s is not a known type' % p)
        
        if not len(changes) == len(all_parts):
            raise ValueError('Some parts between {} cannot be changed')
        
        for (p, v) in changes:
            f = repr
            if to_string:
                f = str
            expr = expr.replace('%s' % p, f(v))
        
        return expr
    
    
    def eval_expr(self, expr, check=None, variables={}):
        logger.debug('EVAL: expression: %s' % expr)
        expr = self.compile(expr, check=check, variables=variables)
        logger.debug('EVAL: exp changed: %s' % expr)
        # final tree
        tree = ast.parse(expr, mode='eval').body
        try:
            r = self.eval_(tree)
        except Exception, exp:
            logger.debug('EVAL: fail to eval expr: %s : %s' % (expr, exp))
            raise
        try:
            logger.debug('EVAL: result: %s' % r)
        except TypeError:  # for r == tuple, try other
            logger.debug('EVAL: result: %s' % str(r))
        return r
    
    
    def eval_(self, node):
        logger.debug('eval_ node: %s => type=%s' % (node, type(node)))
        if isinstance(node, ast.Num):  # <number>
            return node.n
        elif isinstance(node, ast.Str):  # <string>
            return node.s
        elif isinstance(node, ast.List):  # <list>
            return [self.eval_(e) for e in node.elts]
        elif isinstance(node, ast.Tuple):  # <tuple>
            return tuple([self.eval_(e) for e in node.elts])
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
        elif isinstance(node, ast.Subscript):  # {}['key'] access
            # NOTE: the 'key' is node.slice.value.s
            # and the node.value is a ast.Dict, so must be eval_
            _d = self.eval_(node.value)
            v = _d[node.slice.value.s]
            return v
        #        elif isinstance(node, _ast.Attribute):  # o.f() call
        #            # NOTE: for security reason, only accept functons on basic types
        #            print "Attribute:", node, node.__dict__
        #            return None
        #            _d = self.eval_(node.value)
        #            v = _d[node.slice.value.s]
        #            return v
        elif isinstance(node, ast.Call):  # call? dangerous, must be registered :)
            args = [self.eval_(arg) for arg in node.args]
            f = None
            # print 'attr?', isinstance(node.func, ast.Attribute)
            # print 'name?', isinstance(node.func, ast.Name)
            if isinstance(node.func, ast.Name):
                fname = node.func.id
                f = functions.get(fname, None)
                if f is None:
                    logger.error('Eval unknown function %s' % (fname))
                    raise TypeError(node)
            elif isinstance(node.func, ast.Attribute):
                # Attribute is managed only if the base type is a standard one
                _ref_object_node = node.func.value
                if isinstance(_ref_object_node, ast.Dict) or isinstance(_ref_object_node, ast.List) or isinstance(_ref_object_node, ast.Str) or isinstance(_ref_object_node, ast.Set):
                    _ref_object = self.eval_(_ref_object_node)
                    f = getattr(_ref_object, node.func.attr)
                else:
                    logger.error('Eval UNMANAGED (ast.attribute) CALL: %s %s %s is refused' % (node.func, node.func.__dict__, node.func.value.__dict__))
                    raise TypeError(node)
            else:
                logger.error('Eval UNMANAGED (othercall) CALL: %s %s %s is refused' % (node.func, node.func.__dict__, node.func.value.__dict__))
                raise TypeError(node)
            
            if f:
                v = f(*args)
                return v
        else:
            logger.error('Eval UNMANAGED node: %s %s and so is  refused' % (node, type(node)))
            raise TypeError(node)
    
    
    # Try to find the params for a macro pack parameters
    def _found_params(self, m, check):
        # only import it now because if not will do an import loop
        from opsbro.configurationmanager import configmgr
        parts = [m]
        # if we got a |, we got a default value somewhere
        if '|' in m:
            parts = m.split('|', 1)
        change_to = ''
        
        if not check:
            logger.error('Cannot find parameters: %s as we dont have a check' % m)
            return change_to
        
        pack_name = check['pack_name']
        pack_parameters = configmgr.get_parameters_from_pack(pack_name)
        
        logger.debug('Looking for parameter %s into pack %s parameters: %s' % (m, pack_name, pack_parameters))
        
        for p in parts:
            elts = [p]
            if '.' in p:
                elts = p.split('.')
            elts = [e.strip() for e in elts]
            
            # we will try to grok into our cfg_data for the k1.k2.k3 =>
            # self.cfg_data[k1][k2][k3] entry if exists
            (founded, ld) = self._found_params_inside(elts, pack_parameters)
            logger.debug('Did find or not %s into parameters: %s => %s (%s)' % (elts, pack_parameters, founded, ld))
            if founded:
                return ld
        return ''
    
    
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
        
        @http_export('/agent/evaluator/list')
        def get_exports():
            response.content_type = 'application/json'
            res = []
            fnames = functions.keys()
            fnames.sort()
            for fname in fnames:
                f = functions[fname]
                _doc = getattr(f, '__doc__')
                # now get prototype
                
                # only possible if functions have
                if isinstance(f, types.FunctionType):
                    argspec = inspect.getargspec(f)
                    argnames = argspec.args
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
                res.append({'name': fname, 'doc': _doc, 'prototype': prototype, 'group': functions_to_groups[fname]})
            return json.dumps(res)
        
        
        @http_export('/agent/evaluator/eval', method='POST')
        def agent_eval_check():
            response.content_type = 'application/json'
            expr64 = request.POST.get('expr')
            expr = base64.b64decode(expr64)
            v = evaluater.eval_expr(expr)
            return json.dumps(v)


evaluater = Evaluater()
