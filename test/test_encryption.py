#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

from opsbro_test import *

from opsbro.library import libstore
from opsbro.log import cprint

encrypter = libstore.get_encrypter()


class TestEncrypter(OpsBroTest):
    def setUp(self):
        encrypter.load_zone_encryption_key('NTdiN2NlNmE4NTViMTFlNA==', 'internet')
        cprint("ENCRYPTER: %s" % encrypter)
        if encrypter.get_AES() is None:
            raise Exception('The Crypto librairy is missing')
    
    
    def test_encryption(self):
        cprint("ENCRYPTER: %s" % encrypter)
        orig_test = 'Hi I am Alice'
        bobread = encrypter.encrypt(orig_test, dest_zone_name='internet')
        clear = encrypter.decrypt(bobread)
        cprint('CLEAN: %s' % clear)
        self.assert_(clear == orig_test)
        self.assert_(bobread != orig_test)


if __name__ == '__main__':
    unittest.main()
