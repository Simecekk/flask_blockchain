import hashlib
import json
from textwrap import dedent
from time import time
from uuid import uuid4

from flask import Flask, jsonify, request

from urllib.parse import urlparse


class Blockchain(object):
    
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.new_block(previous_hash=1, proof=100)
        self.nodes = set()

    
    def register_node(self, address):
        """
        Add a new node to list of nodes
        :param address: <str> address of new node
        :return None:
        """
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def valid_chain(self, chain):
        """
        Determine if a chain is valid THE one
        :param chain: <list> blockchain
        :return: bool
        """

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print('____________')

            # checks that hash of a block is correct
            if block['previous_hash'] != self.hash(last_block):
                return False

            # checks if proof of work is valid
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        """
        This is our Consensus algorithm, it resolves conflicts
        by replacing our chain with the longest one in the network.
        :return: <bool> True if our chain was replaced, False if not
        """

        neighbours = self.nodes
        new_chain = None


        # We are loogin for chain longer than our
        max_lenght = len(self.chain)

        # Grab all chains from our neighbours nodes
        for node in neighbours:

            response = request.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # Checks if lenght is longer and chain is valid
                if length > max_lenght and self.valid_chain(chain):
                    max_lenght = length
                    new_chain = chain

        if new_chain:
            self.chain = new_chain
            return True
        
        return False


    def proof_of_work(self, last_proof):
        """
        Simple proof of work alghoritm:
        - Find number X , such that hash X * Y containst last 4*0 char where Y is previous X
        - X is new_proof, and Y is previous proof
        :last_proof: <int>
        : reutrn proof: <int>
        """

        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            print(proof)
            proof += 1

        return proof

    def valid_proof(self, last_proof, proof):
        """
        Validates the proof: Does hash sha256(last_proof, proof) contains 4 leading zeros?
        :param: last_proof --> previous proof <int>
        :param: proof --> Current proof <int>
        : return: --> bool
        """

        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()

        print(guess_hash[:4])
        return guess_hash[:4] == "0000"

    def new_block(self, proof, previous_hash=None):
        """
        Create a new Block in the Blockchain
        :param proof: <int> The proof given by the Proof of Work algorithm
        :param previous_hash: (Optional) <str> Hash of the previous block
        :return <dict> New Block
        """
        
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1])
        }


        self.chain.append(block)
        self.current_transactions = []

        return block

    def new_transaction(self, sender, recipient, amount):
        """
        Creates a new transaction to go into the next mined Block
        :param sender: <str> Address of the Sender
        :param recipient: <str> Address of the Recipient
        :param amount: <int> Amount
        :return: <int> The index of the Block that will hold this transaction
        """

        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })
        print(self.current_transactions)
        return self.last_block['index'] + 1 
        
    
    @staticmethod
    def hash(block):
        """
        Creates a SHA-25 hash of a Block
        :param block: <dict> Block
        :return: <str>
        """

        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()
    
    
    @property
    def last_block(self):
        # Returns the last block in the chain
        return self.chain[-1]


# Instatiate our node
app = Flask(__name__)

# Generate a globally unique address for this node
node_identifier = str(uuid4()).replace('-','')

# Instatiate the blockchain
blockchain = Blockchain()

@app.route('/mine', methods=['GET'])
def mine():
    # First we run proof of work alghoritm
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    # we must recieve reward for succesfull mining
    # The sender is 0 to signifiy that this node has mined a new coin
    blockchain.new_transaction(
        sender="0",
        recipient=node_identifier,
        amount=1,
    )

    # Forge the new block by adding it to the chain
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash=previous_hash)

    response = {
        'message': 'New block Forged',
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }

    return jsonify(response), 200


@app.route('/transaction/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    # Checks if all required values for transaction are in POST
    required = ['sender', 'recipient', 'amount']
    print(values)
    if not all(k in values for k in required):
        return 'Missing values', 400

    # Creates new transaction
    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

    response = {'message': f'Your transaction will be added in block {index}'}
    return jsonify(response), 201

@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return 'Please add valid nodes list', 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes were added',
        'total_nodes': list(blockchain.nodes)
    }

    return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():

    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authorative',
            'new_chain': blockchain.chain
        }

    return jsonify(response), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
