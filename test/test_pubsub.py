#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

import copy
import time
import threading
from opsbro_test import *

from opsbro.pubsub import pubsub


class TestPubSub(OpsBroTest):
    def setUp(self):
        self.f1_raised = False
        self.f2_raised = False
        
        self.f3_raised = False
        self.f3_value = None
    
    
    def f1(self):
        self.f1_raised = True
    
    
    def f2(self):
        self.f2_raised = True
    
    
    def f3(self, value_set=''):
        self.f3_raised = True
        if value_set:
            self.f3_value = value_set
    
    
    def test_pubsub(self):
        # Not registerred, so won't trigger it
        pubsub.pub('main')
        self.assert_(self.f1_raised == False)
        
        pubsub.sub('main', self.f1)
        pubsub.pub('main')
        self.assert_(self.f1_raised == True)
        
        # hard reset the bool and do with a two this time
        self.f1_raised = False
        pubsub.sub('main', self.f1)
        pubsub.sub('main', self.f2)
        pubsub.pub('main')
        self.assert_(self.f1_raised == True)
        self.assert_(self.f2_raised == True)
        
        # Now with params
        pubsub.sub('params', self.f3)
        pubsub.pub('params', value_set='set')
        self.assert_(self.f3_raised == True)
        self.assert_(self.f3_value == 'set')


if __name__ == '__main__':
    unittest.main()
