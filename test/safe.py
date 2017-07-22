import sys
import ast
import operator as op
import math

# supported operators
operators = {ast.Add : op.add, ast.Sub: op.sub, ast.Mult: op.mul,
             ast.Div : op.truediv, ast.Pow: op.pow, ast.BitXor: op.xor,
             ast.USub: op.neg, ast.Eq: op.eq}

functions = {'abs': abs}


def assert_(a, b):
    if a != b:
        print 'ERROR: NOT THE SAME', a, b
        return False
    return True


def test(s):
    e = Evaluator()
    v = e.eval_expr(s)
    v2 = eval(s)
    print "Return", v, v2
    b = assert_(v, v2)
    if not b:
        print 'FAIL' * 10, s
        sys.exit(2)


class Evaluator(object):
    def __init__(self):
        pass
    
    
    def eval_expr(self, expr):
        tree = ast.parse(expr, mode='eval').body
        return self.eval_(tree)
    
    
    def eval_(self, node):
        print 'EVAL NODE', node, type(node)
        print dir(node)
        try:
            print node.__dict__
        except:
            pass
        
        if isinstance(node, ast.Num):  # <number>
            print "RETURN", node.n
            return node.n
        elif isinstance(node, ast.BinOp):  # <left> <operator> <right>
            return operators[type(node.op)](self.eval_(node.left), self.eval_(node.right))
        elif isinstance(node, ast.Compare):  # <left> <operator> <right>
            left = self.eval_(node.left)
            print ''
            print "LEFT", left
            
            print ""
            print "NODE", node, node.__dict__
            
            right = self.eval_(node.comparators[0])
            print ''
            print 'RIGHT', right
            
            return operators[type(node.ops[0])](left, right)
        elif isinstance(node, ast.UnaryOp):  # <operator> <operand> e.g., -1
            return operators[type(node.op)](self.eval_(node.operand))
        elif isinstance(node, ast.Name):  # name? try to look at it
            key = node.id
            v = globals().get(key, None)
            print 'VALUE', v
            return v
        elif isinstance(node, ast.Call):  # call? dangerous, must be registered :)
            args = [self.eval_(arg) for arg in node.args]
            print ''
            print "CALL"
            print node.__dict__
            print 'END CALL'
            f = None
            print 'attr?', isinstance(node.func, ast.Attribute)
            print 'name?', isinstance(node.func, ast.Name)
            if isinstance(node.func, ast.Name):
                fname = node.func.id
                print 'FUNCTION CALL', fname
                print node, node.__dict__
                f = functions.get(fname, None)
            elif isinstance(node.func, ast.Attribute):
                print 'WTF F', node.func, node.func.__dict__, node.func.value.__dict__
            
            else:
                print 'UNKNOW FUNC'
                raise TypeError(node)
                #        elif isinstance(node.func, ast.Name):
            
            if f:
                v = f(*args)
                print 'FUNCITON', fname, 'called', args, "returns", v
                return v
        else:
            raise TypeError(node)


evil = "__import__('os').remove('important file')"

try:
    eval_expr(evil)
except Exception, exp:
    print "ERROR", exp

test('2^6')
test('2**6')
test('1 + 2*3**(4^5) / (6 + -7)')
test('1+38')
test('(1+38)==39')

test('abs(-39)')

a = 38
test("(1+a) == abs(-39)")

exp = '{collector.loadaverage.load1} {collector.loadaverage.load5}'
import re

all_parts = re.findall('{.*?}', exp)

for p in all_parts:
    p = p[1:-1]
    print p

print 'OK'
