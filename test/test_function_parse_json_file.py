#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com


from opsbro_test import *

from opsbro.evaluater import evaluater
from opsbro.log import cprint

my_dir = os.path.abspath(os.path.dirname(__file__))


class TestFunction_parse_json_file(OpsBroTestCoreFunctions):
    def test_function(self):
        json_file = os.path.join(my_dir, 'test-files', 'test_function_parse_json_file', 'test-file.json')
        rule = '''parse_json_file('%s')''' % json_file
        cprint("Rule: %s" % rule)
        
        r = evaluater.eval_expr(rule)
        
        expected = {'key': 'value'}
        
        cprint("Expected: %s" % str(expected))
        cprint("Result: %s" % r)
        cprint("Is The same?: %s" % (r == expected))
        self.assert_(r == expected)


if __name__ == '__main__':
    unittest.main()
