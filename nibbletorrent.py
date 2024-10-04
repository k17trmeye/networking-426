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
import threading
import queue
import requests
import math
import socket

# Global Variables
PORT = 8088
HOST = ''
NETID = 'tracejkm'

# Create a new folder
DEST = ''

# Create a list of all the torrent ID's and file names
torrent_id_files = [('0800428c333c811ea3b6f7a0f01ee31c4ba75f85', 'byu.png', 170345), 
                    ('7afd79d76e3ead341af1ad5386e937adc1bb17ea', 'dQw4w9WgXcQ.mp4', 22161810), 
                    ('c218879787f4fd731d91cde380d539b4caaffcc5', 'problem.gif',894235), 
                    ('7de199cad4b953ecf0c9b6d8b72612ddb248890a', 'programming.jpg', 68276),
                    ('b0e0fa6348e41b07da7344f60b62c730da2c07da', 's0csx3lou9941.jpeg', 101643), 
                    ('9e5e5cee673e1d8a4776099659389a3338acdc3f', 's56uf5sn43b81.png',39866)]

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
parser.add_argument("-p", "--port", help="The port to receive peer connections from.", type=int, default=PORT)
parser.add_argument("-d", '--dest', help="The folder to download to and seed from.", type=str, default=DEST)
parser.add_argument("-v", "--verbose", help="Turn on debugging output.", action="store_true")

parser.add_argument("netid", help="Your NetID", type=str)
parser.add_argument("torrent_file", help="The torrent file for the file you want to download.", type=str)
args = parser.parse_args()

# Check to see if DEST argument is provided and exists
if args.dest == '':
    # Default folder if no argument provided
    new_folder_name = 'my_pieces'
    new_folder_path = os.path.join(os.getcwd(), new_folder_name)
    if not os.path.exists(new_folder_path):
        os.makedirs(new_folder_path)
    args.dest = new_folder_path
    if args.verbose:
            logger.info('Folder: %s', args.dest)
else:
    # Get the current working directory
    current_directory = os.getcwd()

    # Create the path to the folder you want to check
    folder_path = os.path.join(current_directory, args.dest)

    # Check if the folder exists
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        if args.verbose:
            logger.info('Folder: %s', args.dest)
    else:
        new_folder_name = 'my_pieces'
        new_folder_path = os.path.join(os.getcwd(), new_folder_name)
        if not os.path.exists(new_folder_path):
            os.makedirs(new_folder_path)
        logger.error('Folder not found, using default folder: %s', new_folder_path)
        args.dest = new_folder_path

# Checks to see what files I have the folder
# List all files in the folder
files = os.listdir(args.dest)

# Create a list of files that I currently have
my_files = []
for file_name in files:
    file_path = os.path.join(args.dest, file_name)

    # Check if the file is a regular file
    if os.path.isfile(file_path):
        my_files.append(file_path)

# Getting personal host name and IP address
h_name = socket.gethostname()
IP_addres = socket.gethostbyname(h_name)

# Printing other info
if args.verbose:
    logger.info("Port: %d", args.port)
    logger.info('NetID: %s', args.netid)
    logger.info('Torrent File: %s', args.torrent_file)
    logger.info("Computer IP Address is: %s\n", IP_addres)

#############################################################################################################
# Parsing the torrent
#############################################################################################################
if args.verbose:
    logger.info('Parsing torrent')

# Initialize global Variables from torrent
torrent_id = ''
tracker_url = ''
file_size = 0
file_name = ''
piece_size = 0
all_pieces = []

# Reading in selected file
file_content = ''
try:
    file_path = args.torrent_file
    with open(file_path, 'r') as file:
        file_content = file.read()
except FileNotFoundError:
    logger.error(f"File not found: {file_path}")
    sys.exit()

# Parsing file line by line to get keys
lines = file_content.splitlines()
collect_pieces = False
for line in lines:
    # Get the torrent_id
    if 'torrent_id' in line:
        torrent_id = line[19:-2]
    # Get the tracker_url  
    if 'tracker_url' in line:
        tracker_url = line[20:-2]
    # Get the file_size
    if 'file_size' in line:
        file_size = line[17:-1]
        file_size = int(file_size)
    # Get the file_name
    if 'file_name' in line:
        file_name = line[18:-2]
    # Get the piece_size
    if 'piece_size' in line:
        piece_size = line[18:-1]
        piece_size = int(piece_size)
    # Marks the end of the list of pieces
    if ']' in line:
        collect_pieces = False
    # Collect each piece and save it to a list of all_pieces
    if collect_pieces:
        new_piece = line[9:-2]
        all_pieces.append(new_piece)
    # Set flag to start collecting each string after in all_pieces
    if 'pieces' in line:
        collect_pieces = True

if args.verbose:
    logger.info('Parsing Completed')
    logger.info('torrent_id: %s', torrent_id)
    logger.info('tracker_url: %s', tracker_url)
    logger.info('file_size: %d', file_size)
    logger.info('file_name: %s', file_name)
    logger.info('piece_size: %d', piece_size)
    logger.info('number of pieces: %d\n', len(all_pieces))

#############################################################################################################
# Functions for downloading, uploading, and contacting tracker
#############################################################################################################
# Variables to be shared between tracker, downloader, and uploader
# List of peers currently connected to
peer_list = queue.Queue()

# Number of peer threads running
num_of_peers = 0

# Version
version_hex = b'\x01'

# Interval to connect to peers
peer_interval = 0

# Types
hello_request_type = b'\x01'
hello_response_type = b'\x02'
piece_request_type = b'\x03'
piece_response_type = b'\x04'
error_response_type = b'\x05'

# Pieces that I currently have
my_pieces_list = []

# Index of pieces I received
my_pieces_index = '0' * len(all_pieces)

# Number of bytes for the pieces
numb_bytes = math.ceil(len(all_pieces) / 8)

#############################################################################################################
# Tracker
# Create url
full_url = (tracker_url + '?peer_id=-ECEN426-' + args.netid + '&ip=' + IP_addres + '&port=' + str(args.port) + '&torrent_id=' + torrent_id)

# Contact the tracker to get JSON file of peers
def contact_tracker():
    if args.verbose:
        logger.info('Running Tracker')

    # Create a tuple of peers in contact with
    current_peers = []

    global peer_interval

    while True:

        # Sending full url request and getting response
        response = requests.get(full_url)

        # Saving response to queue to be accessed by downloader
        new_list = response.json()

        # Create a tuple of peers to contact
        new_peers = []

        # Save the list of peers to select_peers
        for keys in new_list.items():
            if 'peers' in keys:
                new_peers = keys[1]
            elif 'interval' in keys:
                peer_interval = keys[1]
        
        # Printing Interval length
        if args.verbose:
            logger.info('(Tracker) Interval length: %d', peer_interval)

        # Compare new peers to current peers to find new peers
        # If there are no current peers, just assign the peers that I received to current
        if not current_peers:
            current_peers = new_peers
        else:
            temp_list = []
            # Checks to see if the new_peer is already in my current_peers
            for new_peer in new_peers:
                if new_peer in current_peers:
                    continue
                else:
                    temp_list.append(new_peer)
                    if args.verbose:
                        logger.info('(Tracker) Adding new peer: %s', new_peer)
            # Add the temp_list to current_peers
            current_peers += temp_list

        # Loop through list and put into queue
        for new_peer in current_peers: 
            peer_list.put(new_peer)
            if args.verbose:
                logger.info('(Tracker) Adding user: %s', new_peer)
        
        # If I downloaded all the pieces, break out of function
        if len(my_pieces_list) == len(all_pieces):
            if args.verbose:
                logger.info('Closing tracker, all pieces received')
            break

        # Wait 30 seconds before sending another http request
        time.sleep(30)
    
#############################################################################################################
# Downloader
def download_from_tracker():
    if args.verbose:
        logger.info('Running Downloader')

    # Used to hold all the threads of peers I'm connected to
    peer_threads = []
    global num_of_peers
    global file_name
    
    while True:
        if not peer_list.empty():
            # Create a thread for a peer
            if num_of_peers < 5:
                peer = peer_list.get()
                if args.verbose:
                    logger.info('(Downloader) Starting thread for %s', peer[1])
                thread = threading.Thread(target=download_from_peers, args=(peer,))
                thread.start()
                peer_threads.append(thread)
                num_of_peers += 1
            else:
                if args.verbose:
                    logger.error('(Downloader) 5 threads already running, waiting for thread')
                time.sleep(5)

        # If I downloaded all the pieces, break out of function
        if len(my_pieces_list) == len(all_pieces):

            my_pieces_list.sort(key=lambda x: x[1])
            combined_data = b''.join(piece[0] for piece in my_pieces_list)

            # Create file and write to it with the data
            final_destination = os.path.join(args.dest, file_name)
            with open(final_destination, 'wb') as file:
                file.write(combined_data)
            if args.verbose:
                logger.info('Closing downloader, all pieces received')
            break
    return

    # Wait for all threads to finish
    for thread in peer_threads:
        thread.join()


def download_from_peers(peer):
    global num_of_peers

    # Extract the first variable in the list
    peer_connect = peer
    peer_host_port = peer_connect[0]
    peer_host = peer_host_port[:-5]
    peer_port = peer_host_port[-4:]
    
    # Set up TCP connection with peers
    if args.verbose:
        logger.info('(Downloader) Connecting to host: %s', peer_connect[1])
    peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    peer_address = (peer_host, int(peer_port))
    
    try:
        peer_socket.connect(peer_address)

        # Send hello request to peer connection
        torrent_bytes = bytes.fromhex(torrent_id)
        hello_request_bytes = (version_hex + hello_request_type + b'\x00\x14' + torrent_bytes)
        peer_socket.send(hello_request_bytes)

        # Receive hello response
        hello_response = peer_socket.recv(4)
        if b'\x01\x02' not in hello_response[0:2]:
            logger.error('(Downloader) Incorrect hello response')
            peer_socket.close()

        # Receive the rest of the response
        hello_response_length = hello_response[2:]
        hello_response_length = int.from_bytes(hello_response_length, byteorder='big')
        peer_pieces = peer_socket.recv(hello_response_length)

        # Convert the peer pieces to 1s and 0s
        binary_peer_pieces = ''.join(format(byte, '08b') for byte in peer_pieces)
        binary_peer_pieces = binary_peer_pieces[:len(all_pieces)]

        # Counts how many pieces are offered by this peer
        counter = 0
        for char in binary_peer_pieces:
            if char == '1':
                counter += 1
        if args.verbose:
            logger.info('(Downloader) Number of pieces from %s: %d', peer_connect[1], counter)
        
        if counter == 0:
            logger.error('No pieces from peer %s, closing connection', peer_connect[1])
            peer_socket.close()
        else:
            # Save pieces index to temp variable
            temp_binary_peer_pieces = binary_peer_pieces

            # Declare global variable to be used
            global my_pieces_index  

            # Receive all pieces offered by this peer
            while True:
                # Find index of first piece of peer
                piece_index = binary_peer_pieces.find('1')  

                # Edit binary list of pieces
                binary_peer_pieces = binary_peer_pieces[:piece_index] + '0' + binary_peer_pieces[piece_index + 1:] 

                # Check to see if I have this piece already, if I do, start over
                if my_pieces_index[piece_index] == '1':
                    continue  
                else:
                    my_pieces_index = my_pieces_index[:piece_index] + '1' + my_pieces_index[piece_index + 1:]            

                # Request that index from peer
                if args.verbose:
                    logger.info('(Downloader) Receiving piece %d from %s', (piece_index + 1), peer_connect[1])


                piece_index_bytes = piece_index.to_bytes(2, 'big')

                testing = bytes([piece_index_bytes[1]])

                if int(piece_index) <= 255:
                    piece_request = (version_hex + piece_request_type + b'\x00\x01' + testing)
                else:
                    piece_request = (version_hex + piece_request_type + b'\x00\x02' + piece_index_bytes)

                peer_socket.send(piece_request)

                # Receive piece header from peer
                piece_header = peer_socket.recv(4)

                # Checks to see if peer returns error response message
                if b'x\01x\05' in piece_header:
                    logger.error('(Downloader) Piece index out of range')
                    peer_socket.close()
                    break

                # Extract length from header
                piece_length = piece_header[-2:]
                piece_length = int.from_bytes(piece_length, 'big')

                # Receive piece from header
                piece = peer_socket.recv(piece_length)

                # Add piece to list of pieces
                my_pieces_list.append((piece, (piece_index + 1)))            

                if int(binary_peer_pieces) == 0:
                    if args.verbose:
                        logger.info('All pieces received')
                    peer_socket.close()
                    break

    except ConnectionRefusedError as e:
        logger.error(f"(Downloader) Connection refused: {peer_connect[1]}")

    finally:
        num_of_peers -= 1  
        return  

#############################################################################################################
# Uploader
def upload_to_tracker():
    if args.verbose:
        logger.info('Running Uploader')
    
    global numb_bytes
    global my_pieces_index
    global numb_bytes
    global torrent_id
    
    # Create a TCP Socket
    server_socket = socket.socket()
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((IP_addres, args.port))
    server_socket.listen()

    try:
        # Wait for client connection
        while True:
            # Establish connection with the client
            client_socket, client_address = server_socket.accept()
            if args.verbose:
                logger.info('(Uploader) Connection to: %s', client_address)

            while True:
                if args.verbose:
                    logger.info('Uploader waiting for connection')
                # Waiting to receive hello request
                header = client_socket.recv(4)
                
                # Verify Hello header
                if b'\x01\x01' not in header[0:2]:
                    logger.error('Invalid hello request header')
                    client_socket.close()
                    break
                
                # Receive the the torrent ID
                client_torrent_id = client_socket.recv(20)
                client_torrent_id = client_torrent_id.hex()

                # Compare the torrent ID to list to get the name
                requested_file = ''
                requested_file_size = 0
                for torrent in torrent_id_files:
                    if client_torrent_id == torrent[0]:
                        requested_file = torrent[1]
                        requested_file_size = torrent[2]
                
                # Loop through the files that I currently have
                requested_file_path = ''
                for file_path in my_files:
                    if requested_file in file_path:
                        requested_file_path = file_path
                        if args.verbose:
                            logger.info('(Uploader) Requested file found in folder')

                # Open the file that is requested
                file_contents = b''

                try:
                    with open(requested_file_path, 'rb') as file:
                        file_contents = file.read()
                except FileNotFoundError as e:
                    logger.error('File not found')
                    continue
                
                # Create a bitfield of all the pieces that I have
                file_bitfield = (b'1' * math.ceil(requested_file_size/4096)) + (b'0' * 6)

                # Convert the binary string to an integer
                integer_value = int(file_bitfield, 2)

                # Convert the integer to bytes
                byte_representation = integer_value.to_bytes((len(file_bitfield) + 7) // 8, byteorder='big')

                # Create hello response header
                hello_response = b'\x01\x02'

                # Get length of data being sent
                pieces_length = len(byte_representation)
                print(pieces_length)
                hello_response_length = int(file_bitfield, pieces_length)

                # Send hello response to client
                # hello_response += hello_response_length
                client_socket.send(hello_response)

    except BrokenPipeError:
        logger.error("Client disconnected unexpectedly")

    finally:    
        client_socket.close()


#############################################################################################################
# Spawning necessary threads for each task
#############################################################################################################
if args.verbose:
    logger.info('Creating Threads')
download_thread = threading.Thread(target=download_from_tracker)
upload_thread = threading.Thread(target=upload_to_tracker)
contact_thread = threading.Thread(target=contact_tracker)

# Start the threads
if args.verbose:
    logger.info('Starting Threads\n')
download_thread.start()
upload_thread.start()
contact_thread.start()


# Wait for all threads to finish
download_thread.join()
upload_thread.join()
contact_thread.join()
if args.verbose:
    logger.info('All Threads finished')
