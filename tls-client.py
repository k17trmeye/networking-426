import logging
import random
import argparse
import socket
import struct
import time
import sys
import select
import secrets
import os
import crypto_utils as utils
from message import Message, MessageType
from PIL import Image

# Global Variables
PORT = 8087
HOST = "localhost"

# Set up logging
logger = logging.getLogger("simple_example")
logger.setLevel(logging.DEBUG)

# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# create formatter
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# add formatter to ch
ch.setFormatter(formatter)

# add ch to logger
logger.addHandler(ch)

# Parse the arguments
parser = argparse.ArgumentParser()
parser.add_argument("-p", "--port", help="Port to connect to.", type=int, default=PORT)
parser.add_argument("--host", help="Port to connect to.", type=str, default=HOST)
parser.add_argument(
    "-v", "--verbose", help="Turn on debugging output.", action="store_true"
)

parser.add_argument(
    "file",
    help="The file name to save to. It must be a PNG file extension. Use - for\n"
    "stdout.",
    type=str,
)
args = parser.parse_args()

# Printing socket info
if args.verbose:
    logger.info("Port: %d", args.port)
    logger.info("Host: %s", args.host)
    if args.file == '-':
        logger.info('Writing to STDOUT')
    else:
        logger.info("Writing to file: %s", args.file)



# Create a Socket and connect to it
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.connect((args.host, args.port))
if args.verbose:
    logger.info('Socket Created\n')



# Send Hello message
if args.verbose:
    logger.info('Sending Hello message')
hello_message = 0x01
hello_message = hello_message.to_bytes(4, 'little')
server_socket.send(hello_message)

if args.verbose:
    logger.info('Hello message sent\n')



# Certificate
cert_header = server_socket.recv(4)
if args.verbose:
    logger.info('Receiving Server Nonce and Certificate')

# Checking to see if type is certificate
certificate_type = cert_header[:1]
if certificate_type != b'\x02':
    if args.verbose:
        logger.error('Wrong Type')
    server_socket.close()
elif args.verbose:
    logger.info('Type = certificate')

# Making sure the entire length of certificate was received
length = cert_header[1:]
length = int.from_bytes(length, byteorder = 'big')
cert_message = server_socket.recv(length)
if len(cert_message) != length:
    if args.verbose:
        logger.error('Full length not received')
    server_socket.close()
elif args.verbose:
    logger.info('Full certificate data received\n')

# Verifying Certificate and collecting server nonce
certificate = cert_message[32:]
certificate_key = utils.load_certificate(certificate)
if certificate_key == None:
    logger.error('Certificate is not Valid')
    server_socket.close()
elif args.verbose:
    logger.info('Certificate verified\n')



# Generate/Send Nonce
if args.verbose:
    logger.info('Generating/ sending encrypted client nonce')

# Generating Nonce and encrypting w/ server key
nonce = secrets.token_bytes(32)
server_nonce = cert_message[0:32]
server_key = certificate_key.public_key()
nonce_message = utils.encrypt_with_public_key(nonce, server_key)

# Generating header
nonce_type = 0x03
nonce_length = len(nonce_message)
nonce_header = nonce_type.to_bytes(1, 'little')
nonce_header += nonce_length.to_bytes(3, 'little')

# Sending header and encrypted nonce
server_socket.send(nonce_header)
server_socket.send(nonce_message)
if args.verbose:
    logger.info('Nonce header sent')
    logger.info('Nonce message sent\n')



# Generate keys
keys = utils.generate_keys(nonce, server_nonce)
if args.verbose:
    logger.info('Generating keys\n')



# HASH
hash_header = server_socket.recv(4)
if args.verbose:
    logger.info('Receiving server hash')

# Checking to see if type is hash
hash_type = hash_header[:1]
if hash_type != b'\x04':
    if args.verbose:
        logger.error('Wrong Type')
    server_socket.close()
elif args.verbose:
    logger.info('Type == hash')

# Making sure the entire length of hash was received
hash_length = hash_header[1:]
hash_length = int.from_bytes(hash_length, byteorder = 'big')
server_hash = server_socket.recv(hash_length)
if len(server_hash) != hash_length:
    if args.verbose:
        logger.error('Full length not received')
    server_socket.close()
elif args.verbose:
    logger.info('Full hash data received')



# Handle Server Hash
hash_messages = (hello_message + cert_header + cert_message + nonce_header + nonce_message)
server_integrity_key = keys[1]
server_mac = utils.mac(hash_messages, server_integrity_key)
if server_mac != server_hash:
    logger.error('Server hash not equal to server mac')
elif args.verbose:
    logger.info('Server hash verified\n')

# Create client hash
if args.verbose:
    logger.info('Generating client hash')
client_integrity_key = keys[3]
client_mac = utils.mac(hash_messages, client_integrity_key)
# Header
hash_type = 0x04
client_hash_header = hash_type.to_bytes(3, "little")
client_hash_header += b'\x20'
# Sending header and client hash
server_socket.send(client_hash_header)
server_socket.send(client_mac)
if args.verbose:
    logger.info('Client hash header sent')
    logger.info('Client hash sent\n')


# Receiving Encrypted Data
if args.verbose:
    logger.info('Receiving data')

total_data = b''
sequence_number = 0
server_encryption_key = keys[0]
while True:
    # Receive data from TCP Socket
    data = Message.from_socket(server_socket)
    if data == None:
        logger.info('All Data Received')
        server_socket.close()
        break

    # Decrypt data w/ server encryption key
    decrpyted_data = utils.decrypt(data.data, server_encryption_key)

    # Verify sequence number
    seq_num = int.from_bytes(decrpyted_data[:4], byteorder = 'big')
    if seq_num != sequence_number:
        logger.error('Repeated sequence number')
        server_socket.close()
        break
    elif args.verbose:
        logger.info('Correct Sequence Number')
    sequence_number += 1

    # Verify MAC
    data_chunk = decrpyted_data[4:-32]
    data_mac = decrpyted_data[-32:]
    calc_mac = utils.mac(data_chunk, server_integrity_key)
    if calc_mac != data_mac:
        logger.error('Data mac not equal to calculated mac')
        server_socket.close()
        break
    elif args.verbose:
        logger.info('Mac verified')
    # Add received data to total data
    total_data += data_chunk

# Saving data to .png file
output_file = args.file
if output_file == '-':
    sys.stdout.buffer.write(total_data)
else:
    # Save the binary data to a PNG file
    with open(output_file, "wb") as file:
        file.write(total_data)




def main():
    pass


if __name__ == "__main__":
    main()
