from collections import OrderedDict

import binascii

import Crypto
import Crypto.Random
from Crypto.Hash import SHA
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
import base64
import requests
from flask import Flask, jsonify, request, render_template
from functools import reduce
import jsonizer

class Transaction(jsonizer.Jsonizer):
    @classmethod
    def fromJSON(cls, data):
        t = cls('', '', 0, [])	# create a dummy object
        t.__dict__ = data	# copy the dict attributes
        return t

    def __init__(self, sender_address, recipient_address, value, t_in):
        """
            Transaction
        """
        ##set
        self.sender_address = sender_address # To public key του wallet από το οποίο προέρχονται τα χρήματα
        self.receiver_address = recipient_address # To public key του wallet στο οποίο θα καταλήξουν τα χρήματα
        self.amount = value # το ποσό που θα μεταφερθεί
        self.transaction_inputs = t_in # λίστα από Transaction Input

        s_in = 0 if len(t_in) == 0 else sum([value for dic in t_in for (key, value) in dic.items()])

         # sender θελει ρέστα για να μπουν στα utxo
        self.transaction_id = SHA.new(data=Crypto.Random.get_random_bytes(64)).hexdigest() # SHA hash
        self.transaction_outputs = {
            sender_address: {self.transaction_id: s_in - value}, 
            recipient_address: {self.transaction_id: value}
        }
        self.signature = None # παράγεται από το sign_transaction

    def to_dict(self):
        return

    def sign_transaction(self, private_key):
        """
        Sign transaction with private key
        """
        k = RSA.importKey(private_key)                  # import the private key of the sender
        signer = PKCS1_v1_5.new(k)
        t_hash = SHA.new(self.transaction_id.encode())  # create a hash of the transaction id
        s = signer.sign(t_hash)                         # sign the hash
        self.signature = base64.b64encode(s).decode()   # save it with base64 encoding
       