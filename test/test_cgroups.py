#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

import copy
import time
import threading
from opsbro_test import *
from opsbro.log import cprint

try:
    from docker import Client
except ImportError:
    Client = None

from opsbro.misc.cgroups import cgroupmgr


class TestCGroup(OpsBroTest):
    def setUp(self):
        if Client is None:
            self.con = None
            return
        self.con = Client(base_url='unix://var/run/docker.sock')
        self.conts = self.con.containers()
    
    
    def test_cgroup(self):
        if self.con is None:
            return
        
        cprint(self.conts)
        cids = [c['Id'] for c in self.conts]
        print('CIDS: %s' % cids)
        
        metrics = cgroupmgr.get_containers_metrics(cids)
        cprint("METRICS: %s" % metrics)


if __name__ == '__main__':
    unittest.main()
