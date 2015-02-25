#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

import copy
import time
import threading
from kunai_test import *

from kunai.gossip import Gossip
from kunai.broadcast import Broadcaster


class TestGossip(KunaiTest):
    def setUp(self):
        self.gossip = Gossip({}, threading.RLock(), 'localhost', 6768, 'testing-kunai', 0, 'AAAA', ['linux', 'kv'], [], False)

    def test_gossip(self):
        pass

if __name__ == '__main__':
    unittest.main()
