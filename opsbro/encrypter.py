# -*- coding: utf-8 -*-
import sys
import os
import base64
import hashlib
import struct

from .log import LoggerFactory
from .util import bytes_to_unicode, unicode_to_bytes, get_uuid

# Global logger for this part
logger = LoggerFactory.create_logger('gossip')

MAGIC_FLAG = unicode_to_bytes('᠁1')  # ok, won't be easy to see such a thing
MAGIC_FLAG_SIZE = 8  # 4 for the character HEADER + 4 \x00
MAGIC_FLAG_HEADER = struct.pack('%ds' % MAGIC_FLAG_SIZE, MAGIC_FLAG)

KEY_FINGERPRINT_SIZE = 16  # size fo the key finger prints

ENCRYPTED_PACKET_HEADER_SIZE = MAGIC_FLAG_SIZE + KEY_FINGERPRINT_SIZE

GOSSIP_KEY_FILE_FORMAT = '%s.gossip.key'


class RSAKeysPair(object):
    def __init__(self):
        self.private_key = None
        self.public_key = None


class Encrypter(object):
    def __init__(self):
        self.AES = None
        self._gossip_key_fingerprints = {}  # finger print => key
        self._gossip_fingerprints_from_zone = {}  # zone name => key finger print
        self._gossip_zone_from_fingerprint = {}  # key finger print => zone name
        
        # MFK
        self.RSA = None
        self._rsa_keys = {}  # by zones
    
    
    def get_mf_priv_key(self):
        from .gossip import gossiper
        zone_name = gossiper.zone
        key_pair = self._rsa_keys.get(zone_name, None)
        if key_pair is None:
            return None
        
        return key_pair.private_key
    
    
    def get_mf_pub_key(self):
        from .gossip import gossiper
        # TODO: do not only take our zone, but also others
        zone_name = gossiper.zone
        key_pair = self._rsa_keys.get(zone_name, None)
        if key_pair is None:
            return None
        
        return key_pair.public_key
    
    
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
    
    
    def load_zone_encryption_key(self, zone_encryption_key, zone_name):
        AES = self.get_AES()
        if AES is None:
            logger.error('You set an encryption key but cannot import python-crypto module, please install it. Exiting.')
            sys.exit(2)
        try:
            zone_encryption_key = base64.b64decode(zone_encryption_key)
        except ValueError:
            logger.error('The encryption key is invalid, not in base64 format')
            sys.exit(2)
        zone_encryption_key = bytes_to_unicode(zone_encryption_key)
        
        key_fingerprint = self._get_finger_print_from_key(zone_encryption_key)
        self._gossip_key_fingerprints[key_fingerprint] = zone_encryption_key  # so we can listen for packages from this zone
        self._gossip_fingerprints_from_zone[zone_name] = key_fingerprint  # for this zone
        self._gossip_zone_from_fingerprint[key_fingerprint] = zone_name
        logger.debug('Loading the encryption key %s for the zone %s' % (key_fingerprint, zone_name))
    
    
    # We did load a zone, or maybe we need to check that the zone did not change it's key
    # if so, reload it
    def load_or_reload_key_for_zone_if_need(self, zone_name):
        from .configurationmanager import configmgr
        # If the zone have a key, load it into the encrypter so we will be
        # able to use it to exchange with this zone
        # The key can be a file in the zone key directory, with the name of the zone.key
        zone_keys_directory = configmgr.zone_keys_directory
        key_file = os.path.join(zone_keys_directory, GOSSIP_KEY_FILE_FORMAT % zone_name)
        if os.path.exists(key_file):
            logger.debug('The zone %s have a key file (%s)' % (zone_name, key_file))
            with open(key_file, 'rb') as f:
                encryption_key = f.read().strip()
                self.load_zone_encryption_key(encryption_key, zone_name)
        
        self.load_master_keys_if_need(zone_name)
    
    
    def _get_key_from_zone(self, zone_name):
        if zone_name is None or zone_name not in self._gossip_fingerprints_from_zone:
            from .gossip import gossiper
            zone_name = gossiper.zone
            # Maybe our own zone do not have any key, if so, skip encryption
            if zone_name not in self._gossip_fingerprints_from_zone:
                return None
        key_fingerprint = self._gossip_fingerprints_from_zone[zone_name]
        encryption_key = self._gossip_key_fingerprints[key_fingerprint]
        logger.debug('ENCRYPTION: founded the key %s for the zone %s' % (key_fingerprint, zone_name))
        return encryption_key
    
    
    def _is_our_zone_have_a_key(self):
        from .gossip import gossiper
        zone_name = gossiper.zone
        return zone_name in self._gossip_fingerprints_from_zone
    
    
    # Decrypt did fail (not encrypted or malformed. If our zone
    # is encrypted, then we cannot accept this raw_data at all
    def _give_failback_raw_data_is_possible(self, raw_data):
        if self._is_our_zone_have_a_key():
            return None
        return raw_data
    
    
    # We received data from UDP, if we are set to encrypt, decrypt it
    def decrypt(self, raw_data):
        if not raw_data.startswith(MAGIC_FLAG):
            logger.info('Package do not seems to be encrypted: %s' % raw_data)
            # Give uncrypted data only if our zone is not encrypted
            return self._give_failback_raw_data_is_possible(raw_data)
        
        AES = self.get_AES()
        try:
            raw_packet_size = len(raw_data)
            if raw_packet_size - ENCRYPTED_PACKET_HEADER_SIZE <= 0:
                logger.error('Decryption fail: the packet is not valid, do not have enough data after header')
                return None
            
            # print('RAW PACKET SIZE: %s' % raw_packet_size)
            header_and_payload_format = '%ds%ds%ds' % (MAGIC_FLAG_SIZE, KEY_FINGERPRINT_SIZE, raw_packet_size - ENCRYPTED_PACKET_HEADER_SIZE)
            # print('Header payload format: %s' % header_and_payload_format)
            magic_flag, key_fingerprint, encrypted_data = struct.unpack(header_and_payload_format, raw_data)
            key_fingerprint = bytes_to_unicode(key_fingerprint)  # from bytes to unicode as we did store
            
            # print('MAGIC FLAG: %s %s %s %s' % (type(magic_flag), len(magic_flag),  type(MAGIC_FLAG_HEADER), len(MAGIC_FLAG_HEADER) ))
            if magic_flag != MAGIC_FLAG_HEADER:
                logger.error('Decryption fail: the magic flag is wrong %s' % magic_flag)
                return None
            # print('HEADER: %s' % magic_flag)
            
            # print('Key finger print %s' % key_fingerprint)
            
            logger.debug('DECRYPT: did receive a key %s from zone: %s' % (key_fingerprint, self._gossip_zone_from_fingerprint.get(key_fingerprint)))
            
            encryption_key = self._gossip_key_fingerprints.get(key_fingerprint, None)
            if encryption_key is None:
                logger.error('Decryption fail: the packet is valid, but we do not know about this key fingerprint (%s)' % key_fingerprint)
                return None
            
            # Be sure the data is x16 lenght
            if len(encrypted_data) % 16 != 0:
                raw_data += ' ' * (-len(encrypted_data) % 16)
            cypher = AES.new(encryption_key, AES.MODE_ECB)
            decrypted_data = cypher.decrypt(encrypted_data).strip()
            return bytes_to_unicode(decrypted_data)
        except Exception as exp:
            logger.error('Decryption fail: %s' % exp)
            return None
    
    
    def encrypt(self, data, dest_zone_name=None):
        encryption_key = self._get_key_from_zone(dest_zone_name)
        if encryption_key is None:  # we do not have valid key for this zone, cannot encrypt
            return unicode_to_bytes(data)
        
        AES = self.get_AES()
        
        # Be sure the data is x16 lenght
        if len(data) % 16 != 0:
            data += ' ' * (-len(data) % 16)
        # print('TO encrypt data size: %s' % len(data))
        
        try:
            cypher = AES.new(encryption_key, AES.MODE_ECB)
            encrypted_data = cypher.encrypt(data)
            encrypted_data_size = len(encrypted_data)
            key_fingerprint = self._get_finger_print_from_key(encryption_key)
            
            final_packet_format = '%ds%ds%ds' % (MAGIC_FLAG_SIZE, KEY_FINGERPRINT_SIZE, encrypted_data_size)
            # print('STRUCT FORMAT %s' % final_packet_format)
            final_packet = struct.pack(final_packet_format, unicode_to_bytes(MAGIC_FLAG), unicode_to_bytes(key_fingerprint), encrypted_data)
            # print('Final packet %s' % final_packet)
            # print('Final packet size: %s' % len(final_packet))
            return final_packet
        except Exception as exp:
            logger.error('Encryption fail:', exp)
            return u''
    
    
    def load_master_keys_if_need(self, zone_name):
        from .configurationmanager import configmgr
        
        RSA = self.get_RSA()
        private_key_file = '%s.private.key' % zone_name
        public_key_file = '%s.public.key' % zone_name
        private_key_path = os.path.join(configmgr.zone_keys_directory, private_key_file)
        public_key_path = os.path.join(configmgr.zone_keys_directory, public_key_file)
        if not os.path.exists(private_key_path) and not os.path.exists(public_key_path):
            return
        
        # Now we will need to load them
        if RSA is None:
            logger.error('You set a master public/private key but but cannot import python-rsa module, please install it. Exiting.')
            sys.exit(2)
        
        if not zone_name in self._rsa_keys:
            self._rsa_keys[zone_name] = RSAKeysPair()
        
        key_pair = self._rsa_keys[zone_name]
        
        # Same for master fucking key PRIVATE
        if os.path.exists(private_key_path):
            with open(private_key_path, 'r') as f:
                buf = unicode_to_bytes(f.read())  # the RSA lib need binary
            try:
                mfkey_priv = RSA.PrivateKey.load_pkcs1(buf)
                key_pair.private_key = mfkey_priv
            except Exception as exp:
                logger.error('Invalid master private key at %s. (%s) Exiting.' % (private_key_path, exp))
                sys.exit(2)
            logger.info('Master private key file %s is loaded for the zone %s' % (private_key_path, zone_name))
        
        # Same for master fucking key PUBLIC
        if os.path.exists(public_key_path):
            # let's try to open the key so :)
            with open(public_key_path, 'r') as f:
                buf = unicode_to_bytes(f.read())  # the RSA lib need binary
            try:
                mfkey_pub = RSA.PublicKey.load_pkcs1(buf)
                key_pair.public_key = mfkey_pub
            except Exception as exp:
                logger.error('Invalid master public key at %s. (%s) Exiting.' % (public_key_path, exp))
                sys.exit(2)
            logger.info('Master public key file %s is loaded' % public_key_path)


    def generate_challenge(self, zone_name):
        challenge_string = get_uuid()
        RSA = self.get_RSA()
        public_key = self.get_mf_pub_key()
        raw_encrypted_string = RSA.encrypt(unicode_to_bytes(challenge_string), public_key)  # encrypt 0=dummy param not used
        encrypted_challenge = bytes_to_unicode(base64.b64encode(raw_encrypted_string))  # base64 returns bytes
        return challenge_string, encrypted_challenge
    

encrypter = None


def get_encrypter():
    global encrypter
    if encrypter is None:
        logger.debug('Lazy creation of the encrypter class')
        encrypter = Encrypter()
    return encrypter
