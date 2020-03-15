import binascii

import Crypto
import Crypto.Random
from Crypto.Hash import SHA
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5

import hashlib
import json
from time import time
from urllib.parse import urlparse
from uuid import uuid4
import jsonizer


class Wallet(jsonizer.Jsonizer):
    def __init__(self, addressp):
        ##set
        key = RSA.generate(2048)
        self.public_key = key.publickey().exportKey().decode('utf-8')
        self.private_key = key.exportKey().decode('utf-8')
        self.addressp = addressp
