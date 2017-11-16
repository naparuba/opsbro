#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

from opsbro_test import *

from opsbro.evaluater import evaluater


class TestFunction_is_plain_file(OpsBroTestCoreFunctions):
    def test_function(self):
        rule = '''is_plain_file('%s')''' % os.path.abspath(__file__)
        print "Rule: %s" % rule
        
        r = evaluater.eval_expr(rule)
        
        expected = True
        
        print "Expected: %s" % str(expected)
        print "Result: %s" % r
        print "Is The same?: %s" % (r == expected)
        self.assert_(r == expected)


if __name__ == '__main__':
    unittest.main()
