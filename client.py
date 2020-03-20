from rest import get_ip_address
import requests
from transaction import Transaction
import jinja2
import re
import os

ip = get_ip_address('eth1')
last_command = ''
project_dir = os.path.dirname(os.path.realpath(__file__))
template_dir = project_dir + '/templates'

def load_template(filename):
    templateLoader = jinja2.FileSystemLoader(searchpath=template_dir)
    templateEnv = jinja2.Environment(loader=templateLoader)
    TEMPLATE_FILE = filename
    return templateEnv.get_template(TEMPLATE_FILE)

def view_transactions():
    '''View latest valid block transactions'''
    r = requests.get('http://' + ip + ':5000/latest_transactions')
    list_of_transactions = [Transaction.fromJSON(i) for i in r.json()]
    template = load_template("transaction.jinja")
    i=1
    for t in list_of_transactions:
        print(template.render(dict(t.__dict__), i=i))
        i += 1
        

def create_transaction(receiver, amount):
    '''Create new transaction for receiver_id.'''
    d = {
            'id': receiver,
            'amount': amount
    }
    r = requests.post(
        'http://' + ip + ':5000/create_transaction',
        json=d
    )
    print(r.status_code, r.text)

def command_not_found(cmd):
    print('Command not found: "%s". Type "help" to see available commands.' % cmd)

def get_balance():
    '''Get wallet balance'''
    r = requests.get('http://' + ip + ':5000/node/balance')
    print('Balance: ', r.text, end = "")

def get_help():
    '''Print this message'''
    print('Available commands:')
    length = max([len(key) for key in dispatch])
    f = '{0:<%d} : {1}' % (length)
    for (key, value) in dispatch.items():
        print(f.format(key, value.__doc__))

def get_pubs():
    '''Get public keys for each node'''
    r = requests.get('http://' + ip + ':5000/pub_key_mapping')
    template = load_template('pub_key.jinja')
    for (key, value) in r.json().items():
        print(template.render(i=value, key=key))

def run_transactions(filename):
    '''Execute transaction from file <filename>'''
    print('Run transactions from ', filename)
    try:
        f = open(filename, 'r')
    except Exception as e:
        print(e)
        return
    
    for line in f:
        matched = re.match(r'id([0-9]*) ([0-9]*)', line)
        if matched is not None:
            (id, amount) = matched.groups()
            print('create transaction ', id, amount)
            create_transaction(id, amount)
        else:
            print('Invalid syntax in file.')
            break

    f.close()
    return

def run_last_command():
    '''Run latest run command'''
    global last_command
    run_command(last_command)

def show_last_command():
    '''Show last run command'''
    global last_command
    print(last_command)

dispatch = {
    'view': view_transactions,
    'balance': get_balance,
    'pub': get_pubs,
    'help': get_help,
    't <reveiver_id> <amount>': create_transaction,
    'run <filename>': run_transactions,
    'last': run_last_command,
    'sl': show_last_command
}

def run_command(command):
    global last_command
    try:
        dispatch[command]()
        if command.startswith('run'): last_command = command
    except KeyError:
        matched_create = re.match(r't ([0-9].*) ([0-9].*)', command)
        matched_run = re.match(r'run (.+)', command)
        if matched_create is not None:
            r,a = matched_create.groups()
            create_transaction(r, a)
        elif matched_run:
            (filename,) = matched_run.groups()
            run_transactions(filename)
        else:
            command_not_found(command)
        if command.startswith('run'): last_command = command

def client():
    while (1):
        command = str(input('\033[1;32mclient>\033[0m '))
        run_command(command)

if __name__ == '__main__':
    client()