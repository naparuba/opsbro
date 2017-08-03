#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

import copy
import time
import threading
from pprint import pprint
from opsbro_test import *

from opsbro.dockermanager import dockermgr


class TestDocker(OpsBroTest):
    def setUp(self):
        dockermgr.connect()
        dockermgr.load_containers()
    
    
    def test_docker(self):
        if dockermgr.con is None:
            return
        
        dockermgr.compute_stats()
        time.sleep(1)
        dockermgr.compute_stats()


if __name__ == '__main__':
    unittest.main()
