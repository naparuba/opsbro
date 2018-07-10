#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

from opsbro_test import *

from opsbro.evaluater import evaluater
from opsbro.log import cprint


class TestFunction_is_plain_file(OpsBroTestCoreFunctions):
    def test_function(self):
        rule = '''is_plain_file('%s')''' % os.path.abspath(__file__)
        cprint("Rule: %s" % rule)
        
        r = evaluater.eval_expr(rule)
        
        expected = True
        
        cprint("Expected: %s" % str(expected))
        cprint("Result: %s" % r)
        cprint("Is The same?: %s" % (r == expected))
        self.assert_(r == expected)


if __name__ == '__main__':
    unittest.main()
