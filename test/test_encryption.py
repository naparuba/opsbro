#!/usr/bin/env python
# Copyright (C) 2014:
#    Gabes Jean, naparuba@gmail.com

from opsbro_test import *

from opsbro.library import libstore
from opsbro.log import cprint
from opsbro.util import unicode_to_bytes, bytes_to_unicode

encrypter = libstore.get_encrypter()


class TestUDPEncrypter(OpsBroTest):
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


class TestRSAEncrypter(OpsBroTest):
    def setUp(self):
        RSA = encrypter.get_RSA()
        master_key_priv = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'test-files', 'test-executors', 'internet.private.key')
        with open(master_key_priv, 'rb') as f:
            buf = unicode_to_bytes(f.read())
        self.mfkey_priv = RSA.PrivateKey.load_pkcs1(buf)
        
        master_key_pub = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'test-files', 'test-executors', 'internet.public.key')
        with open(master_key_pub, 'rb') as f:
            buf = unicode_to_bytes(f.read())
        self.mfkey_pub = RSA.PublicKey.load_pkcs1(buf)
    
    
    def test_encryption(self):
        orig_test = 'Hi I am Alice'
        RSA = encrypter.get_RSA()
        encrypted = RSA.encrypt(unicode_to_bytes(orig_test), self.mfkey_pub)  # encrypted thanks to public
        decrypted = bytes_to_unicode(RSA.decrypt(encrypted, self.mfkey_priv))  # decrypte with private
        
        print('Original:%s(%s)\nDecrypted:%s(%s)' % (orig_test, type(orig_test), decrypted, type(decrypted)))
        self.assert_(decrypted == orig_test)
        self.assert_(encrypted != orig_test)
        
        print('OK')


if __name__ == '__main__':
    unittest.main()
