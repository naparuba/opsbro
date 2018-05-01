#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

import traceback
from opsbro_test import *

from opsbro.evaluater import evaluater


class TestEvaluater(OpsBroTest):
    def setUp(self):
        pass
    
    
    def test_evaluator(self):
        rules = [
            {'rule': '1+1', 'expected': 2},
            {'rule': '2-1', 'expected': 1},
            {'rule': '10*10', 'expected': 100},
            {'rule': '100/10', 'expected': 10},
            {'rule': '2**3', 'expected': 8},
            {'rule': '16^4', 'expected': 20},
            {'rule': '"azerty"', 'expected': "azerty"},
            {'rule': '("a"=="a")', 'expected': True},
            {'rule': '("a"!="b")', 'expected': True},
            {'rule': '10 > 5', 'expected': True},
            {'rule': '10 < 5', 'expected': False},
            {'rule': '10 >= 10', 'expected': True},
            {'rule': '10 <= 10', 'expected': True},
            {'rule': '13 % 2', 'expected': 1},
            {'rule': '(1 == 1) and (2 == 3)', 'expected': False},
            {'rule': '(1 == 1) or (2 == 3)', 'expected': True},
            {'rule': '10 | 3', 'expected': 11},
            {'rule': '10 ^ 3', 'expected': 9},
            {'rule': 'True and not False', 'expected': True},
            {'rule': 'not ("a"=="a")', 'expected': False},
            {'rule': '{"k":"v"}', 'expected': {'k': 'v'}},
            {'rule': '(1, 2, 3)', 'expected': (1, 2, 3)},
            {'rule': '(1, 2,3) == (1,2,3)', 'expected': True},
            {'rule': '"PI %.2f" % 3.14', 'expected': "PI 3.14"},
            
            # Dicts
            {'rule': '{"k":"v"}["k"]', 'expected': 'v'},
            {'rule': '"k" in {"k":"v"}', 'expected': True},
            {'rule': '{"k":"v"}.values()', 'expected': ["v"]},
            
            # Math functions
            {'rule': 'min([1,2,3])', 'expected': 1},
            {'rule': 'max([1,2,3])', 'expected': 3},
            {'rule': 'abs(-1)', 'expected': 1},
            {'rule': 'sum([1,2,3])', 'expected': 6},
            
            # List & strings functions
            {'rule': '"v2" in ["v1", "v2"]', 'expected': True},
            {'rule': 'sorted(["v2", "v1"])', 'expected': ["v1", "v2"]},
            {'rule': 'len([1,2,3])', 'expected': 3},
            
            # dict.values()
            {'rule': 'sorted({"k":"v", "k2":"v2"}.values())', 'expected': ["v", "v2"]},
            
            # Sets
            {'rule': 'set(["v1", "v2", "v2"])', 'expected': set(['v1', 'v2'])},
    
            # Do not execute functions at right in And if the first part is False
            {'rule': 'False and missing_function()', 'expected': False},
            # Do not execute functions at right in Or if the first part is True
            {'rule': 'True or missing_function()', 'expected': True},

        ]
        for r in rules:
            print "\n\n" + "#" * 30
            rule = r['rule']
            expected = r['expected']
            try:
                r = evaluater.eval_expr(rule)
            except Exception as exp:
                r = traceback.format_exc()
            print "Rule: %s" % rule
            print "Expected: %s" % str(expected)
            print "Result: %s" % str(r)
            print "Is The same?: %s" % (r == expected)
            self.assert_(r == expected)


if __name__ == '__main__':
    unittest.main()
