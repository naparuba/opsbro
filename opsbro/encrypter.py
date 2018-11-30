# -*- coding: utf-8 -*-
import sys
import os
import base64
import hashlib
import struct

from .log import LoggerFactory
from .util import bytes_to_unicode, unicode_to_bytes

# Global logger for this part
logger = LoggerFactory.create_logger('security')

MAGIC_FLAG = unicode_to_bytes('᠁1')  # ok, won't be easy to see such a thing
MAGIC_FLAG_SIZE = 8  # 4 for the character HEADER + 4 \x00
MAGIC_FLAG_HEADER = struct.pack('%ds' % MAGIC_FLAG_SIZE, MAGIC_FLAG)

KEY_FINGERPRINT_SIZE = 16  # size fo the key finger prints

ENCRYPTED_PACKET_HEADER_SIZE = MAGIC_FLAG_SIZE + KEY_FINGERPRINT_SIZE


class Encrypter(object):
    def __init__(self):
        self.encryption_key = None
        self.AES = None
        self.RSA = None
        self.key_fingerprints = {}
    
    
    def get_RSA(self):
        if self.RSA is not None:
            return self.RSA
        # Cannot take RSA from Crypto because on centos6 the version
        # is just toooooo old :(
        try:
            import rsa as RSA
            self.RSA = RSA
        except ImportError:
            # NOTE: rsa lib import itself as RSA, so we must hook the sys.path to be happy with this...
            _internal_rsa_dir = os.path.join(os.path.dirname(__file__), 'misc', 'internalrsa')
            sys.path.insert(0, _internal_rsa_dir)
            # ok so try the mist one
            try:
                import opsbro.misc.internalrsa.rsa as RSA
                self.RSA = RSA
            except ImportError:
                # even local one fail? arg!
                self.RSA = None
                # so now we did import it, refix sys.path to do not have misc inside
                # sys.path.pop(0)
        return self.RSA
    
    
    def get_AES(self):
        if self.AES is not None:
            return self.AES
        try:
            from Crypto.Cipher import AES
        except ImportError:
            AES = None
        self.AES = AES
        return AES
    
    
    def _get_finger_print_from_key(self, key):
        return hashlib.sha1(unicode_to_bytes(key)).hexdigest()[:KEY_FINGERPRINT_SIZE]  # 16 char for the default size
    
    
    def load_encryption_key(self, encryption_key):
        if not encryption_key:
            self.encryption_key = None
            return
        
        AES = self.get_AES()
        if AES is None:
            logger.error('You set an encryption key but cannot import python-crypto module, please install it. Exiting.')
            sys.exit(2)
        try:
            encryption_key = base64.b64decode(encryption_key)
        except ValueError:
            logger.error('The encryption key is invalid, not in base64 format')
            sys.exit(2)
        self.encryption_key = bytes_to_unicode(encryption_key)
        
        key_fingerprint = self._get_finger_print_from_key(self.encryption_key)
        self.key_fingerprints[key_fingerprint] = self.encryption_key
    
    
    # We received data from UDP, if we are set to encrypt, decrypt it
    def decrypt(self, raw_data):
        # We do nto manage encryption at all
        if not self.encryption_key:
            return raw_data
        AES = self.get_AES()
        logger.debug('DECRYPT with ' + self.encryption_key)
        try:
            raw_packet_size = len(raw_data)
            if raw_packet_size - ENCRYPTED_PACKET_HEADER_SIZE <= 0:
                logger.error('Decryption fail: the packet is not valid, do not have enough data after header')
                return u''
            
            # print('RAW PACKET SIZE: %s' % raw_packet_size)
            header_and_payload_format = '%ds%ds%ds' % (MAGIC_FLAG_SIZE, KEY_FINGERPRINT_SIZE, raw_packet_size - ENCRYPTED_PACKET_HEADER_SIZE)
            # print('Header payload format: %s' % header_and_payload_format)
            magic_flag, key_fingerprint, encrypted_data = struct.unpack(header_and_payload_format, raw_data)
            key_fingerprint = bytes_to_unicode(key_fingerprint)  # from bytes to unicode as we did store
            
            # print('MAGIC FLAG: %s %s %s %s' % (type(magic_flag), len(magic_flag),  type(MAGIC_FLAG_HEADER), len(MAGIC_FLAG_HEADER) ))
            if magic_flag != MAGIC_FLAG_HEADER:
                logger.error('Decryption fail: the magic flag is wrong %s' % magic_flag)
                return u''
            # print('HEADER: %s' % magic_flag)
            
            # print('Key finger print %s' % key_fingerprint)
            
            encryption_key = self.key_fingerprints.get(key_fingerprint, None)
            if encryption_key is None:
                logger.error('Decryption fail: the packet is valid, but we do not know about this key fingerprint (%s)' % key_fingerprint)
                return u''
            
            # Be sure the data is x16 lenght
            if len(encrypted_data) % 16 != 0:
                raw_data += ' ' * (-len(encrypted_data) % 16)
            cypher = AES.new(encryption_key, AES.MODE_ECB)
            decrypted_data = cypher.decrypt(encrypted_data).strip()
            return bytes_to_unicode(decrypted_data)
        except Exception as exp:
            logger.error('Decryption fail:', exp)
            return u''
    
    
    def encrypt(self, data):
        if not self.encryption_key:
            return data
        AES = self.get_AES()
        logger.debug('ENCRYPT with ' + self.encryption_key)
        
        # Be sure the data is x16 lenght
        if len(data) % 16 != 0:
            data += ' ' * (-len(data) % 16)
        # print('TO encrypt data size: %s' % len(data))
        try:
            cypher = AES.new(self.encryption_key, AES.MODE_ECB)
            encrypted_data = cypher.encrypt(data)
            encrypted_data_size = len(encrypted_data)
            key_fingerprint = self._get_finger_print_from_key(self.encryption_key)
            
            final_packet_format = '%ds%ds%ds' % (MAGIC_FLAG_SIZE, KEY_FINGERPRINT_SIZE, encrypted_data_size)
            # print('STRUCT FORMAT %s' % final_packet_format)
            final_packet = struct.pack(final_packet_format, unicode_to_bytes(MAGIC_FLAG), unicode_to_bytes(key_fingerprint), encrypted_data)
            # print('Final packet %s' % final_packet)
            # print('Final packet size: %s' % len(final_packet))
            return final_packet
        except Exception as exp:
            logger.error('Encryption fail:', exp)
            return u''


encrypter = None


def get_encrypter():
    global encrypter
    if encrypter is None:
        logger.debug('Lazy creation of the encrypter class')
        encrypter = Encrypter()
    return encrypter
