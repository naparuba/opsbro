#!/usr/bin/env python

import sys
import time
import imp
import datetime
import os
import string
import re
import random
import unittest
import copy

# import the opsbro library from the parent directory
import __import_opsbro

del __import_opsbro
import opsbro

from opsbro.log import logger


class __DUMMY:
    def add(self, obj):
        pass


class _Unittest2CompatMixIn:
    def assertNotIn(self, member, container, msg=None):
        self.assertTrue(member not in container)
    
    
    def assertIn(self, member, container, msg=None):
        self.assertTrue(member in container)
    
    
    def assertIsInstance(self, obj, cls, msg=None):
        self.assertTrue(isinstance(obj, cls))
    
    
    def assertRegexpMatches(self, line, pattern):
        r = re.search(pattern, line)
        self.assertTrue(r is not None)
    
    
    def assertIs(self, obj, cmp, msg=None):
        self.assertTrue(obj is cmp)


class OpsBroTest(unittest.TestCase, _Unittest2CompatMixIn):
    def setUp(self):
        pass
    
    
    def setup_with_file(self, path):
        pass


class OpsBroTestCoreFunctions(OpsBroTest):
    def setUp(self):
        print "** loading core function module"
        my_dir = os.path.abspath(os.path.dirname(__file__))
        core_functions_dir = os.path.join(my_dir, '..', 'data', 'global-configuration', 'packs', 'core-functions', 'module')
        print "** From directory", core_functions_dir
        sys.path.insert(0, core_functions_dir)
        m = imp.load_source('module___titi___toto___tata', os.path.join(core_functions_dir, 'module.py'))
        print "** Core functionns module is loaded:", m
        self.assert_(m.CoreFunctionsModule is not None)


if __name__ == '__main__':
    unittest.main()
