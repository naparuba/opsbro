try:
    from Crypto.Cipher import AES
    from Crypto.PublicKey import RSA
except ImportError:
    AES = None
    RSA = None


from kunai.log import logger    

    
class Encrypter(object):
    def __init__(self):
        self.encryption_key = None

    def load(self, encryption_key):
        self.encryption_key = encryption_key


    # We received data from UDP, if we are set to encrypt, decrypt it
    def decrypt(self, data):
        if not self.encryption_key:
            return data
        logger.debug('DECRYPT with '+self.encryption_key)
        # Be sure the data is x16 lenght
        if len(data) % 16 != 0:
            data += ' ' * (-len(data) % 16)
        try:
            cyph = AES.new(self.encryption_key, AES.MODE_ECB)
            ndata = cyph.decrypt(data).strip()
            return ndata
        except Exception, exp:
            logger.error('Decryption fail:', exp, part='gossip')
            return ''

        
    def encrypt(self, data):
        if not self.encryption_key:
            return data
        logger.debug('ENCRYPT with '+self.encryption_key)
        # Be sure the data is x16 lenght
        if len(data) % 16 != 0:
            data += ' ' * (-len(data) % 16)
        try:
            cyph = AES.new(self.encryption_key, AES.MODE_ECB)
            ndata = cyph.encrypt(data)
            return ndata
        except Exception, exp:
            logger.error('Encryption fail:', exp, part='gossip')
            return ''
        
    
encrypter = Encrypter()
