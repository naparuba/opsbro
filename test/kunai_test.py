#!/usr/bin/env python

import sys
import time
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


if __name__ == '__main__':
    unittest.main()
