#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

import copy
import time
import threading
from kunai_test import *

from kunai.encrypter import encrypter



class TestEncrypter(KunaiTest):
    def setUp(self):
        encrypter.load('NTdiN2NlNmE4NTViMTFlNA==')


    def test_encryption(self):
        orig_test = 'Hi I am Alice'
        bobread = encrypter.encrypt(orig_test)
        print bobread
        clear = encrypter.decrypt(bobread)
        print clear
        self.assert_(clear == orig_test)

if __name__ == '__main__':
    unittest.main()
