import Crypto
import Crypto.Random
from Crypto.Hash import SHA256
import jsonizer

class Block(jsonizer.Jsonizer):
    @classmethod
    def fromJSON(cls, data):
        b = cls(0, '', 0)    # create a dummy object
        b.__dict__ = data    # copy the dict attributes
        return b
        
    def __init__(self, bid, previous_hash, timestamp):
        ##set
        self.id = bid # coming from node.chain.size
        self.previous_hash = previous_hash # coming from the last block in the chain
        self.timestamp = timestamp
        self.nonce = 0 # calculated with mine
        self.transactions = [] # transaction ids that are in the block
        self.calculate_hash() # calculate the hash
        self.mined = False
    
    # SHA.new(str(hash(b)).encode()).hexdigest()
    def __hash__(self):
        return hash((
            self.id, self.previous_hash, 
            self.timestamp, self.nonce, 
            ''.join(self.transactions)
        ))

    def calculate_hash(self):
        # Produce the hash for this block
        self.hash = SHA256.new(str(hash(self)).encode()).hexdigest()

    # transaction to add to blockchain
    def add_transaction(self, tid):
        #add a transaction to the block
        self.transactions.append(tid)