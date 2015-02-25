#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

import copy
import time
import threading
from kunai_test import *

try:
    from docker import Client
except ImportError:
    Client = None


from kunai.cgroups import cgroupmgr
    

class TestCGroup(KunaiTest):
    def setUp(self):
        if Client is None:
            self.con = None
            return
        self.con = Client(base_url='unix://var/run/docker.sock')
        self.conts = self.con.containers()        

    
    def test_cgroup(self):
        if self.con is None:
            return
            
        print self.conts
        cids = [c['Id'] for c in self.conts]
        print 'CIDS', cids

        metrics = cgroupmgr.get_containers_metrics(cids)
        print "METRICS", metrics

        
        
if __name__ == '__main__':
    unittest.main()
