#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

import threading
import tempfile

from opsbro_test import *
from opsbro.gossip import gossiper


class TestGossip(OpsBroTest):
    def setUp(self):
        # We need to have a valid path for data
        from opsbro.configurationmanager import configmgr
        configmgr.data_dir = tempfile.gettempdir()
        gossiper.init({}, threading.RLock(), '127.0.0.1', 6768, 'testing', 'super testing', 1, 'QQQQQQQQQQQQQQQQQQ', [], [], False, 'private', True)
    
    
    def test_gossip(self):
        pass


if __name__ == '__main__':
    unittest.main()
