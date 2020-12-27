"""aes_encrypt.py

created 14-may-2019 by richb@instantlinux.net
"""

import base64
import hashlib

from Cryptodome.Cipher import AES
from Cryptodome.Random import get_random_bytes

BLOCK_SIZE = 16


class AESEncrypt(object):
    """AES encryption for strings

    Provides easier-to-use AES CBC encrypt/decrypt operations for strings

    Args:
      secret (str): passphrase (suggest at least 16 characters)
    """
    def __init__(self, secret):
        self.private_key = hashlib.sha256(secret.encode('utf-8')).digest()

    def encrypt(self, raw):
        """encrypt a string

        Args:
          raw (str): object to be encrypted
        Returns:
          bytes: encrypted object
        """
        iv = get_random_bytes(AES.block_size)
        cipher = AES.new(self.private_key, AES.MODE_CBC, iv)
        return base64.b64encode(iv + cipher.encrypt(self._pad(raw).encode()))

    def decrypt(self, enc):
        """decrypt an object

        Args:
          enc (bytes): encrypted object
        Returns:
          str: decrypted string
        """
        enc = base64.b64decode(enc)
        iv = enc[:16]
        cipher = AES.new(self.private_key, AES.MODE_CBC, iv)
        return self._unpad(cipher.decrypt(enc[16:]))

    @staticmethod
    def _pad(s):
        return s + (BLOCK_SIZE - len(s) % BLOCK_SIZE) * chr(
            BLOCK_SIZE - len(s) % BLOCK_SIZE)

    @staticmethod
    def _unpad(s):
        return s[:-ord(s[len(s) - 1:])]
