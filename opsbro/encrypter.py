import sys
import os

try:
    from Crypto.Cipher import AES
except ImportError:
    AES = None

# Cannot take RSA from Crypto because on centos6 the version
# is just toooooo old :(
try:
    import rsa as RSA
except ImportError:
    # NOTE: rsa lib import itself as RSA, so we must hook the sys.path to be happy with this...
    _internal_rsa_dir = os.path.join(os.path.dirname(__file__), 'misc', 'internalrsa')
    sys.path.insert(0, _internal_rsa_dir)
    # ok so try the mist one
    try:
        import opsbro.misc.internalrsa.rsa as RSA
    except ImportError:
        # even local one fail? arg!
        RSA = None
        # so now we did import it, refix sys.path to do not have misc inside
        # sys.path.pop(0)

from opsbro.log import LoggerFactory

# Global logger for this part
logger = LoggerFactory.create_logger('security')


class Encrypter(object):
    def __init__(self):
        self.encryption_key = None
    
    
    def load(self, encryption_key):
        self.encryption_key = encryption_key
    
    
    # We received data from UDP, if we are set to encrypt, decrypt it
    def decrypt(self, data):
        if not self.encryption_key:
            return data
        logger.debug('DECRYPT with ' + self.encryption_key)
        # Be sure the data is x16 lenght
        if len(data) % 16 != 0:
            data += ' ' * (-len(data) % 16)
        try:
            cyph = AES.new(self.encryption_key, AES.MODE_ECB)
            ndata = cyph.decrypt(data).strip()
            return ndata
        except Exception, exp:
            logger.error('Decryption fail:', exp)
            return ''
    
    
    def encrypt(self, data):
        if not self.encryption_key:
            return data
        logger.debug('ENCRYPT with ' + self.encryption_key)
        # Be sure the data is x16 lenght
        if len(data) % 16 != 0:
            data += ' ' * (-len(data) % 16)
        try:
            cyph = AES.new(self.encryption_key, AES.MODE_ECB)
            ndata = cyph.encrypt(data)
            return ndata
        except Exception, exp:
            logger.error('Encryption fail:', exp)
            return ''


encrypter = Encrypter()
