from block import Block
from wallet import Wallet
from transaction import Transaction
import requests
import threading
# import requests_async as requests
import time
import Crypto.Random
from Crypto.Hash import SHA
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
import base64
import jsonizer
from functools import reduce

sem = threading.Semaphore()
sem_t = threading.Semaphore()

MINING_DIFFICULTY = 4 # how many zeros should a hash have in order to be accepted
CAPACITY = 1 # how many transactions a block should contain

class Node(jsonizer.Jsonizer):
    ''' Class describing a node in the network
    
        Attributes:
        id                  The id of the node got from bootstrap node
        wallet              The wallet of the node
        addressp            The communication information ip:port
        chain               Array of blocks "blockchain"
        ring                All the information about the nodes of the network
        mining              Boolean attribute indication whether or not the node is mining its candidate block
        candidate_block     The next block that will get mined when CAPACITY transactions reach the node
        pub_map             Dictionary from public_key -> node id 
        bootstrap_info      The communication info of the bootstrap node
        alltransaction      All the transactions processed by the network '''
    def __init__(self, addressp, bootstrap_info):
        self.chain = [] # this is the current blockchain that the node sees from bootstrap
        self.alltransactions = {} # from bootstrap node
        self.id = None # id this is done during registration of the node to the ring
        self.addressp = addressp
        self.bootstrap_info = bootstrap_info
        self.wallet = None # is set when calling create_wallet
        self.ring = {}   # here we store information for every node, as its id, its address (ip:port) its public key and its balance
        self.mining = False
        # add this in order to calculate the pub_map only 1 time when the ring is updated
        # to avoid unnecessary calculations
        self.pub_map = {}
        self.candidate_block = Block(0, '', time.time())

    # map with format 'pub_key' -> id in order to be able to update the utxos
    # using the pub_keys in the initial ring
    def pub_key_mapping(self):
        '''Produce the public_key -> node id dictionary using the ring'''
        return {value['pub_key'] : key for (key, value) in self.ring.items()}
    
    def create_new_block(self, save=True):
        '''Create new block by resetting the attributes of the candidate block'''
        ph = 1 if len(self.chain) == 0 else self.chain[-1].hash
        b = Block(len(self.chain), ph, time.time())
        if save: self.candidate_block = b
        return b

    def create_wallet(self):
        '''Create wallet for the node'''
        self.wallet = Wallet(self.addressp)
        return self.wallet

    # this function in the bootstrap node should do
    # other things that normal nodes
    def register_node_to_ring(self):
        '''Communicate with the bootstrap node in order to insert the node to the ring'''
        self.create_wallet()
        d = {
            'pub_key' : self.wallet.public_key,
            'communication_info' : self.addressp
        }
        r = requests.post('http://' + self.bootstrap_info + '/bootstrap/connect', json = d)
        data = r.json()
        self.ring = data['ring']
        self.id = data['id']
        self.pub_map = self.pub_key_mapping()

        # deserialize blocks in chain
        self.chain = [Block.fromJSON(i) for i in data['chain']]
        
        print('Chain is valid ==> ', self.validate_chain(self.chain))
        # deserialize transactions in alltransactions
        self.alltransactions = {key:Transaction.fromJSON(value) for (key, value) in data['alltransactions'].items()}

        # store candidate_block
        self.candidate_block = Block.fromJSON(data['candidate_block'])

        # get pending transactoin validate it and add it to
        # - all transactions
        # - candidate block
        # t = Transaction.fromJSON(data['pending_transaction'])
        # print(self.validate_transaction(t))
        
        # self.process_transaction(t)
        return

    # returns the necessary utxos for funding the amount
    # to transfer
    # raise Exception for insufficient funds
    def find_funds(self, amount):
        '''Find available utxos in order to satisfy the amount (Used when creating a transaction)'''
        if not amount > 0: raise Exception('Invalid amount to transfer.')
        s = 0
        t_in = []
        i = 0
        while s < amount and i < len(self.ring[self.id]['utxos']):
            utxo = self.ring[self.id]['utxos'][i]
            t_in.append(utxo)
            s += list(utxo.values())[0]
            i += 1

        if s < amount:
            raise Exception('Wallet does not have funds for this transaction.')
        else:
            return t_in
    
    # receiver is wallet
    def create_transaction(self, receiver, value, find_funds=True):
        '''Create a new transaction and sign it if there are funds to satisfy the amount'''
        if self.wallet.public_key == receiver and find_funds: 
            raise Exception('Cannot send transfer to own wallet')
        
        t_in = self.find_funds(value) if find_funds else []
        transaction = Transaction(self.wallet.public_key, receiver, value, t_in)
        transaction.sign_transaction(self.wallet.private_key)
        return transaction

    # skip id in the ring used in the start because the
    # new node is not up
    # @t: transaction to broadcast
    def broadcast_transaction(self, t, skip=None):
        '''Broadcast transaction to the network using the ring '''
        print('Broadcasting transaction')
        for n in self.ring:
            # skip the one that did the request because its not up yet
            if (n == skip or n == self.id): 
                continue
            fire_and_forget(
                'http://' + self.ring[n]['communication_info'] + '/transaction/new', 
                t.__dict__)
        self.process_transaction(t)
    
    def validate_transaction(self, t):
        '''Validate the transaction by validating its signature
        and transaction inputs'''
    # use of signature and NBCs balance
        k = RSA.importKey(t.sender_address)
        verifier = PKCS1_v1_5.new(k)
        try:
            ret = verifier.verify(SHA.new(t.transaction_id.encode()), base64.b64decode(t.signature.encode()))
        except (ValueError, TypeError):
            return False
        
        # check the utxos of the sender
        nodeid = self.pub_map[t.sender_address]
        ret &= sublist(self.ring[nodeid]['utxos'], t.transaction_inputs)
        return ret

    def add_transaction_to_block(self, tid):
        '''Add transaction to block if its possible. If it is not mine
        the candidate block in order to make space for the new transaction.
        This is done synchronized among threads.'''
        print('add transaction to block')
        sem.acquire()
        # loop until the candidate block transaction are full
        # Now check the capacity and mine block
        # and broadcast it if the last block does not have the same id as
        # the candidate block, if it does somebody already mined it
        while len(self.candidate_block.transactions) >= CAPACITY and not self.candidate_block.mined:
            self.mine_block(tid)
            # if noone mined before me broadcast
            # if some1 mined the block the candidate block would be
            # none so try catch
            if self.candidate_block.mined:
                print('I am the one broadcasting my block')
                self.broadcast_block(self.candidate_block)
            else:
                print('I do not broadcast my block cause it was discarded')

        # check if the transaction is in the chain already
        if tid not in [id for b in self.chain for id in b.transactions]:
            print('adding transaction to block', tid)
            self.candidate_block.add_transaction(tid)
        else:
            print('Transaction already in the blockchain')
        print('end')
        sem.release()
        return

    # validates the transaction 
    # updates the utxos of the transaction participants
    # adds the transaction to alltransactions
    # adds the transaction to the candidate block
    def process_transaction(self, t):
        '''Process transaction.'''
        print('Process transaction\n', t.transaction_id)
        if (self.validate_transaction(t)):
            # fix the utxos that the transaction indicates in the ring !!!
            # remove the transaction inputs from the sender utxos
            sender_id = self.pub_map[t.sender_address]
            sem_t.acquire()
            
            self.ring[sender_id]['utxos'] = [utxo for utxo in self.ring[sender_id]['utxos'] if utxo not in t.transaction_inputs]
            
            # update the utxos with the transaction outputs
            for (key, value) in t.transaction_outputs.items():
                noid = self.pub_map[key]
                self.ring[noid]['utxos'].append(value)
            
            sem_t.release()
            self.alltransactions[t.transaction_id] = t
            self.add_transaction_to_block(t.transaction_id)
        else:
            print('Invalid transaction')
    
    def get_balance(self):
        '''Find the nodes balance according to its utxos in the ring'''
        utxos = self.ring[self.id]['utxos']
        return sum([ list(i.values())[0] for i in utxos])

    def process_block(self, b, remote=False):
        '''Process new block internal or remote.'''
        print('Processing new block remote =', remote)
        if (self.validate_block(b)):
            print('Is valid')
            self.chain.append(b)
        else:
            print('Not valid')
            self.valid_chain()

        # get the cut between the transaction of the processed block
        # and the current candidate block
        cut = [t for t in self.candidate_block.transactions if t not in b.transactions]
        if (self.mining and remote):
            print('Aborting mining of block\n', self.candidate_block.__dict__)
        self.mining = False
        self.create_new_block()
        self.candidate_block.transactions = cut
        
        
        

    # change the nonce of the block in order to
    # achieve the zeroes
    def mine_block(self, tid):
        '''Mine candidate block. Stop if mine is succesfull or from process block remote
        when new block from the network is available'''
        #while self.mining: pass # like semaphore
        self.mining = True # set that we are currently mining our candidate block
        start_t = time.time()
        print('MINING CANDIDATE BLOCK BECAUSE OF %s\n' % tid, self.candidate_block.__dict__)
        try:
            # for some reason the block 
            while not self.candidate_block.hash.startswith(MINING_DIFFICULTY*'0'):
                #if len(self.candidate_block.transactions) == 0 : raise AttributeError # got block from network
                if not self.mining: raise AttributeError # self.mining is set to False when we process a block
                self.candidate_block.nonce =  Crypto.Random.random.getrandbits(32)
                self.candidate_block.calculate_hash()
            
            self.candidate_block.mined = True
            self.candidate_block.mining_time = time.time() - start_t
            print('Candidate block mined')
            print(self.candidate_block.__dict__)
        except AttributeError:
            print('STOP MINING')
        return

    def broadcast_block(self, b):
        '''Broadcast mined block the network'''
        print('Broadcasting block ----> ', b.__dict__)
        for n in self.ring:
            # skip the one that did the request because its not up yet
            # do not broadcast to this node because it does the candidate block to be none
            if (n == self.id):
                continue
            try:
                requests.post(
                    'http://' + self.ring[n]['communication_info'] + '/block/new', 
                    json=b.__dict__)
            except Exception:
                # this will happened if a host is down or not yet up when nodes first included
                # in the ring
                continue
        self.process_block(b) # den auksanei to id se periptwsi pou erthei mined block tin wra tou broadcast afou to painroume apo to chain
        return

    def validate_block(self, b):
        '''Validate block by validating its proof of work and the previous hash'''
        ret = b.hash.startswith(MINING_DIFFICULTY*'0')
        ret &= b.previous_hash == self.chain[-1].hash
        return ret

    # def validate_block_in_chain(self, b):
    #     ret = b.hash.startswith(MINING_DIFFICULTY*'0')

    def validate_chain(self, chain):
        '''Validate chain by validating all the blocks in the chain '''
        # check for the longer chain accroose all nodes
        return all([self.chain[i].previous_hash == self.chain[i-1].hash for i in range(len(self.chain)-1, 1, -1)])

    #concencus functions
    def valid_chain(self):
        '''Find the bigger chain in the network'''
        # check for the longer chain accroose all nodes
        # take all the chains and keep the longer
        print('Getting longer chain')
        chains = []
        for n in self.ring:
            # skip the one that did the request because its not up yet
            r = requests.get('http://' + self.ring[n]['communication_info'] + '/node/chain')
            chains.append(r.json())

        longer_chain = max(chains, key=len)
        self.chain = [Block.fromJSON(b) for b in longer_chain]
        return

    def resolve_conflicts(self):
        #resolve correct chain
        return

def sublist(lst1, lst2):
    '''Check whether or not lst1 is a sublist of lst2'''
    ls1 = [element for element in lst1 if element in lst2]
    ls2 = [element for element in lst2 if element in lst1]
    return ls1 == ls2

def request_task(url, data):
    requests.post(url, json=data)

def fire_and_forget(url, json):
    '''Send request post without waiting for the response
    Used when broadcasting'''
    threading.Thread(target=request_task, args=(url, json)).start()