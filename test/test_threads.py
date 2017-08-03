#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

import copy
import time
from opsbro_test import *

from opsbro.threadmgr import ThreadMgr

i = 0


def f():
    global i
    print "I am a thread"
    i += 1
    time.sleep(0.5)


class TestThreads(OpsBroTest):
    def setUp(self):
        pass
    
    
    def test_thread(self):
        T = ThreadMgr()
        T.create_and_launch(f, name='F')
        self.assert_(len(T.all_threads) == 1)
        T.check_alives()
        time.sleep(1)
        T.check_alives()
        self.assert_(len(T.all_threads) == 0)
        self.assertIs(i, 1)


if __name__ == '__main__':
    unittest.main()
