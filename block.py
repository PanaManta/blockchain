import Crypto
import Crypto.Random
from Crypto.Hash import SHA256
import jsonizer


class Block(jsonizer.Jsonizer):
    ''' Class describing a block in the blockchain

        Attributes:
        id              The id of the block (coming from node.chain.size)
        previous_hash   The hash of the previous block in the chain
        timestamp       The timestamp of creation of the block
        nonce           The proof of work
        transactions    Array of transaction ids that the block contains
        mined           Boolean attribute indicating that the block is mined
        mining_time     The time it took for the block to be mined
    '''
    @classmethod
    def fromJSON(cls, data):
        '''Create a new block object from json
        
        Arguments:
        data    The json from which to create the object'''
        b = cls(0, '', 0)    # create a dummy object
        b.__dict__ = data    # copy the dict attributes
        return b
        
    def __init__(self, bid, previous_hash, timestamp):
        ''' Contstructor'''
        self.id = bid # coming from node.chain.size
        self.previous_hash = previous_hash # coming from the last block in the chain
        self.timestamp = timestamp
        self.nonce = 0 # calculated with mine
        self.transactions = [] # transaction ids that are in the block
        self.calculate_hash() # calculate the hash
        self.mined = False
        self.mining_time = 0 # milliseconds
    
    def __hash__(self):
        '''Return the hash of the block using the attributes:
        id, previous_hash, timestamp, nonce, transactions '''
        return hash((
            self.id, self.previous_hash, 
            self.timestamp, self.nonce, 
            ''.join(self.transactions)
        ))

    def calculate_hash(self):
        '''Use SHA256 algorithm to hash the __hash__ and produce the
        hash for the block in hex representation'''
        h = SHA256.new(str(hash(self)).encode())
        self.hash = h.hexdigest()
        del h

    # transaction to add to blockchain
    def add_transaction(self, tid):
        '''Add transaction to block '''
        self.transactions.append(tid)