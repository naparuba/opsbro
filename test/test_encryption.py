#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

from opsbro_test import *

from opsbro.library import libstore

encrypter = libstore.get_encrypter()


class TestEncrypter(OpsBroTest):
    def setUp(self):
        encrypter.load('NTdiN2NlNmE4NTViMTFlNA==')
        print "ENCRYPTER", encrypter
    
    
    def test_encryption(self):
        print "ENCRYPTER", encrypter
        orig_test = 'Hi I am Alice'
        bobread = encrypter.encrypt(orig_test)
        print "BOREAD", bobread
        clear = encrypter.decrypt(bobread)
        print "CLEAR", clear
        self.assert_(clear == orig_test)


if __name__ == '__main__':
    unittest.main()
