from Crypto.PublicKey import RSA
import jsonizer


class Wallet(jsonizer.Jsonizer):
    ''' Class describing a wallet in the blockchain
    
        Attributes:
        public_key      Produced public key using the RSA algorithm "utf-8" representation
        private_key     Producted private key using the RSA algorithm "utf-8" representation
        addressp        The communication information of the wallet'''
    def __init__(self, addressp):
        ''' Constructor
                
                Generates key pair'''
        key = RSA.generate(2048)
        self.public_key = key.publickey().exportKey().decode('utf-8')
        self.private_key = key.exportKey().decode('utf-8')
        self.addressp = addressp
