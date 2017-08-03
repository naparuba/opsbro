#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

import copy
import time
import threading
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
            {'rule': '"a" in ["a","b"]', 'expected': True},
            {'rule': '{"k":"v"}', 'expected': {'k': 'v'}},
            # NOTMANAGE {'rule': '{"k":"v"}["k"]', 'expected': 'v'},
        ]
        for r in rules:
            print "\n\n" + "#" * 30
            rule = r['rule']
            expected = r['expected']
            try:
                r = evaluater.eval_expr(rule)
            except Exception, exp:
                r = traceback.format_exc()
            print "Rule: %s" % rule
            print "Expected: %s" % expected
            print "Result: %s" % r
            print "Is The same?: %s" % (r == expected)
            self.assert_(r == expected)


if __name__ == '__main__':
    unittest.main()
