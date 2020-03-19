import binascii

import Crypto
import Crypto.Random
from Crypto.Hash import SHA
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
import base64
import jsonizer

class Transaction(jsonizer.Jsonizer):
    ''' Class describing a transaction in the blockchain
    
        Attributes:
        transaction_id          The id of the transaction produced using SHA algorithm
        sender_address          The public key of the sender node
        receiver_address        The public key of the reciepient node
        amount                  The amount to be transfered
        transaction_inputs      Array of utxos to be used
        transaction_outputs     The resulting utxos for the sender and receiver nodes
    '''
    @classmethod
    def fromJSON(cls, data):
        '''Create a new block object from json
        
        Arguments:
        data    The json from which to create the object'''
        t = cls('', '', 0, [])	# create a dummy object
        t.__dict__ = data	# copy the dict attributes
        return t

    def __init__(self, sender_address, recipient_address, value, t_in):
        '''Constructor
        '''
        self.sender_address = sender_address
        self.receiver_address = recipient_address
        self.amount = value
        self.transaction_inputs = t_in

        s_in = 0 if len(t_in) == 0 else sum([value for dic in t_in for (key, value) in dic.items()])

        self.transaction_id = SHA.new(data=Crypto.Random.get_random_bytes(64)).hexdigest() # SHA hash
        self.transaction_outputs = {
            sender_address: {self.transaction_id: s_in - value}, 
            recipient_address: {self.transaction_id: value}
        }
        self.signature = None

    def sign_transaction(self, private_key):
        """Sign transaction with private key
        """
        k = RSA.importKey(private_key)                  # import the private key of the sender
        signer = PKCS1_v1_5.new(k)
        t_hash = SHA.new(self.transaction_id.encode())  # create a hash of the transaction id
        s = signer.sign(t_hash)                         # sign the hash
        self.signature = base64.b64encode(s).decode()   # save it with base64 encoding
       