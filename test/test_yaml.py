#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com


from opsbro_test import *

import os
import sys
from opsbro.yamlmgr import yamler

'''
import opsbro.misc

p = os.path.join(os.path.dirname(opsbro.misc.__file__), 'internalyaml')
sys.path.insert(0, p)

import ruamel.yaml as yaml
'''


class TestYaml(OpsBroTest):
    def setUp(self):
        pass
    
    
    def test_evaluator(self):
        s = '''
        # Pre comment
        # on two lines
        - super string # is this a valid comment
        - k1: blabla
          k2: 36.000
          k3:
              # is this a valid comment
              - sub 1
              - sub 2
        # ending comment
        '''
        
        data = yamler.loads(s)
        
        self.assert_(data[0] == 'super string')
        self.assert_(data[1]['k1'] == 'blabla')
        self.assert_(data[1]['k2'] == 36.00)
        
        buf = yamler.dumps(data)
        print "BUF", buf


if __name__ == '__main__':
    unittest.main()
