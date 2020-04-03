import requests
import time
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import threading

from block import Block
from transaction import Transaction
from node import Node
from node import MINING_DIFFICULTY
from node import CAPACITY
from jencoder import Encoder

### JUST A BASIC EXAMPLE OF A REST API WITH FLASK
CURRENT_NODE_ID = 1
app = Flask(__name__)
app.json_encoder = Encoder
CORS(app)
node = None
#.......................................................................................
client_transactions = 0
network_transactions = 0
sem_n = threading.Semaphore()
sem_c = threading.Semaphore()

START_BUDGET = 1000
# URI that the nodes connect with their public keys
# Functionallity:
# - add the node to the node ring
# - give the new node his id and the current node ring TODO: give the current blockchain transactions
# - broadcast the new node ring to everybody else
# - TODO: create new transaction for giving 100 NBC to the new node
@app.route('/bootstrap/connect', methods=['POST'])
def node_connect():
    global CURRENT_NODE_ID
    global node
    data = request.json
    node.ring[str(CURRENT_NODE_ID)] = data
    node.ring[str(CURRENT_NODE_ID)]['utxos'] = []    
    broadcast_ring(str(CURRENT_NODE_ID)) # true for skipping the current node id because its not up yet
    

    # create a transaction for transfering 100NBC to the
    # newly inserted node
    # broadcast it to the ones that are inside the ring
    # this way the one that creates the transaction can
    # get it and verify it like the other ones
    # maybe we need to transfer the block that is currently
    # created and waits to be mined
    # we want to transfer 100 so find the utxos to fill this nbcs
    t = node.create_transaction(data['pub_key'], 100)
    print(node.validate_transaction(t))
    response = {
        'id': str(CURRENT_NODE_ID),
        'ring': node.ring,
        'chain': node.chain,
        'alltransactions': node.alltransactions,
        'candidate_block': node.candidate_block, # the until now candidate block
    }

    # check if the candidate block should be mined
    # and if yes wait until is mined and return the correct chain
    # to the newly added node
    if (len(node.candidate_block.transactions) == CAPACITY):
        # wait until the candidate_block gets mined by the network
        node.broadcast_transaction(t, str(CURRENT_NODE_ID))
        while (t.transaction_id not in node.candidate_block.transactions ): pass
    else:
        node.broadcast_transaction(t, str(CURRENT_NODE_ID))

    response = {
        'id': str(CURRENT_NODE_ID),
        'ring': node.ring,
        'chain': node.chain,
        'alltransactions': node.alltransactions,
        'candidate_block': node.candidate_block, # the until now candidate block
    }
    CURRENT_NODE_ID += 1
    
    return jsonify(response), 200

@app.route('/n_transactions', methods=['GET'])  # Get the number of transactions
def get_client_transctions():
    global network_transactions, client_transactions, node
    blockchain = node.chain
    all_t = len([t for b in blockchain for t in b.transactions])
    candidate_block_t = len(node.candidate_block.transactions)
    json = {
        'client': client_transactions,
        'network': network_transactions,
        
        'all_transactions': all_t + candidate_block_t #len(node.alltransactions.keys())
    }
    return jsonify(json), 200

# This is the route that listens for ring updates
# for every node in the ring
@app.route('/ring/update', methods=['POST'])
def update_ring():
    global node
    node.ring = request.json['ring']
    node.pub_map = node.pub_key_mapping()
    return '', 200

@app.route('/pub_key_mapping', methods=['GET']) # Get pub_key mapping
def get_pub_key_mapping():
    global node
    return jsonify(node.pub_map), 200

@app.route('/ring', methods=['GET'])    # Get the ring of the system
def get_ring():
    global node
    return jsonify(node.ring), 200

@app.route('/node', methods=['GET'])    # Get the state of the node at this point
def get_node():
    global node
    return jsonify(node), 200
    
@app.route('/transaction/new', methods=['POST'])
def new_transaction():
    print('Got new transaction')
    global node, network_transactions
    # do this with semaphore to avoid memory leak?
    sem_n.acquire()
    network_transactions += 1
    t = Transaction.fromJSON(request.json)
    node.process_transaction(t)
    sem_n.release()
    return '', 200

@app.route('/create_transaction', methods=['POST'])
def create_transaction():
    global node, client_transactions
    sem_c.acquire()
    client_transactions += 1
    sem_c.release()
    data = request.json
    print('Got request for new transaction:', data['id'], data['amount'])
    try:
        r_pub_key = node.ring[data['id']]['pub_key']
        t = node.create_transaction(r_pub_key, int(data['amount']))
        node.broadcast_transaction(t)
    except KeyError:
        return 'Id "'+ data['id'] +'" not found in the ring', 405
    except Exception as e:
        return str(e), 406
    
    return 'Created', 200

@app.route('/block/new', methods=['POST'])
def new_block():
    print('GOT new mined block')
    global node
    print(request.json)
    b = Block.fromJSON(request.json)
    node.process_block(b, True)
    return '', 200

@app.route('/node/chain', methods=['GET']) # Get current blockchain
def get_chain():
    global node
    return jsonify(node.chain), 200

@app.route('/node/balance', methods=['GET'])    # Get the nodes balance
def get_balance():
    global node
    return jsonify(node.get_balance()), 200

@app.route('/latest_transactions', methods=['GET']) # Get the latest_block transctions
def get_latest_transactions():
    global node
    lb = node.chain[-1]
    latest_trans = [node.alltransactions[key] for key in lb.transactions]
    return jsonify(latest_trans), 200

@app.route('/get_balances', methods=['GET']) # Get the balances for all the nodes as this backend sees
def get_balances():
    global node
    json = {}
    for i in node.ring:
        utxos = node.ring[i]['utxos']
        json[i] = sum([ list(i.values())[0] for i in utxos])

    json['sum'] = sum([json[i] for i in json])
    return jsonify(json), 200

# get the mining time average MTA
@app.route('/mta', methods=['GET']) # Get the mining time average
def get_mta():
    global node
    avg = sum([b.mining_time for b in node.chain])/len(node.chain)
    return jsonify(avg), 200

# define skip = true if we want to skip the
# the CURRENT_NODE_ID when broadcasting
def broadcast_ring(skip = None):
    for n in node.ring:
        # skip the one that did the request because its not up yet
        if (n == skip): 
            continue
        requests.post(
            'http://' + node.ring[n]['communication_info'] + '/ring/update', 
            json={
                'ring': node.ring
            })

# TODO: create the genesis block
# which has 1 transaction transfering 500 NBC to the wallet of bootstrap
# so add a UTXO to the bootstrap
def bootstrap_setup(node):
    node.create_wallet()
    node.id = '0'
    node.ring[node.id] = {
        'communication_info': host + ':' + str(port), 
        'pub_key' : node.wallet.public_key,
        'utxos' : []
    }
    node.pub_map = node.pub_key_mapping()
    
    init_t = node.create_transaction(node.wallet.public_key, START_BUDGET, False)

    # override the created outputs cause of genesis transaction
    init_t.transaction_outputs = {
        init_t.receiver_address: {init_t.transaction_id: START_BUDGET}
    }

    # create a new transaction for the genesis block don't broadcast
    # create a block with only this transaction
    if (node.validate_transaction(init_t)):
        b = node.create_new_block(False) # don't save this block as a candidate block
        b.add_transaction(init_t.transaction_id)
        # we want nonce = 0 so calculate a valid hash 
        # with timestamp change
        start_t = time.time()
        while not b.hash.startswith(MINING_DIFFICULTY*'0'):
            b.timestamp = time.time()
            b.calculate_hash()

        b.mining_time = time.time() - start_t
        # add the first transaction to the transaction dictionary
        node.alltransactions[init_t.transaction_id] = init_t
        b.mined = True
        # add the block to the chain
        node.chain.append(b)
        node.create_new_block()
        # add the result of the genesis transaction
        # to the utxos of the receiver_address
        for (key, value) in init_t.transaction_outputs.items():
                noid = node.pub_map[key]
                node.ring[noid]['utxos'].append(value)
    else:
        print('Invalid')

    return node


def get_ip_address(ifname):
    import socket
    import fcntl
    import struct
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', bytes(ifname[:15], 'utf-8'))
    )[20:24])

# run it once for every node
if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    parser.add_argument('-b', '--bootstrap', default='192.168.0.1:5000', type=str, help="Ip of the bootstrap")
    parser.add_argument('--ifname', default='eth1', type=str, help='Interface to host the app (Default eth1)')
    args = parser.parse_args()
    port = args.port
    host = get_ip_address(args.ifname)
    bootstrap = args.bootstrap
    node = Node(host + ':' + str(port), bootstrap) # create a new node

    # if we are on bootstrap node don't call the register_node_to_ring()
    if (bootstrap == str(host) + ':' + str(port)):
        print('## We are the bootstrap node')
        node = bootstrap_setup(node)
    else:
        print('## We are a regular node')
        node.register_node_to_ring()
    
    print(node.__dict__)
    app.run(host=host, port=port, threaded=True)