import logging
import random
import argparse
import socket
import struct
import time
import sys
import select
import os
import threading
import queue

PORT = 8085
HOST = ''
FOLDER = '.'
chunk_size = 1024

# Set up logging
logger = logging.getLogger('simple_example')
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
parser.add_argument("-p", "--port", help="port to bind to", type=int, default=PORT)
parser.add_argument(
    "-v", "--verbose", help="turn on debugging output", action="store_true"
)
parser.add_argument(
    "-d", "--delay", help="add a delay for debugging purposes", action="store_true"
)
parser.add_argument(
    "-f", "--folder", help="folder from where to serve from", default=FOLDER
)
parser.add_argument(
    "-c", "--concurrency", help='concurrency methodology to use', choices = ['thread','thread-pool', 'single-thread'], default='thread'
)
args = parser.parse_args()


# Make sure that there is a folder
current_directory = os.getcwd()
contents = os.listdir(current_directory)
folders = [
    item for item in contents if os.path.isdir(os.path.join(current_directory, item))
]
folder_found = False
if args.folder != ".":
    for folder in folders:
        print(folder, ' = ', args.folder)
        if args.folder == folder:
            folder_found = True

    if folder_found == False:
        args.folder = "."
        if args.verbose:
            logger.error("Folder not found, using default")    

# Print info if verbose enabled
if args.verbose:
    logger.setLevel(logging.INFO)
    logger.info("Verbose Enabled")
    logger.info("Folder: %s", args.folder)
    logger.info("Port: %s", args.port)
    logger.info("Host: %s", HOST)
    logger.info("Method: %s", args.concurrency)

# Create a Socket
sock = socket.socket()
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((HOST, args.port))
sock.listen()
if args.verbose:
    logger.info("Socket Created")

################################################################################################################################################################
# Function parsing/sending request
################################################################################################################################################################
def request_handler(client):
    message = b''
    while True:
        try:
            if args.verbose:
                logger.info("Waiting for recv()")

            while not message.endswith(b'\r\n\r\n'):
                chunk = client.recv(1024)  
                if not chunk:
                    break
                message += chunk

            if not message:
                raise BrokenPipeError  

            if args.verbose:
                logger.info("Response Received\n")

            # Parsing the headers
            message = message.decode()
            request = message.split("\n")
            if args.verbose:
                logger.info("Parsing HTTP headers")
                for line in request:
                    if len(line) <= 1:
                        continue
                    logger.info(line)

            # Searching the files within the folder given
            method = request[0]
            method = method.split()
            folder_path = os.path.abspath(args.folder)
            filename = method[1]
            filename = filename[1:]
            file_found = False
            for folder_file in os.listdir(folder_path):
                if folder_file == filename:
                    file_found = True
                    if args.verbose:
                        logger.info("File Found")
                    break

            # If delay is enabled, pause for 5 seconds
            if args.delay:
                if args.verbose:
                    logger.info("Delaying for 5 seconds")
                time.sleep(5)

            # Send back header
            header_response = "HTTP/1.1 200 OK\r\n"
            client.send(header_response.encode())
            if args.verbose:
                logger.info('First HTTP Header Sent')

            # Making sure that the request is only GET
            if method[0] != "GET":
                file_path = "www/405.html"
                file_size = os.path.getsize(file_path)
                content_len = "Content-Length: " + str(file_size) + "\r\n"
                client.send(content_len.encode())
                file = open(file_path, "rb")
                data = file.read(chunk_size)
                client.send(data)
                file.close()
                if args.verbose:
                    logger.error('Error 405: Not a GET request')
                return

            if args.verbose:
                logger.info("GET Request")

            # If file_found flag wasn't set to true,
            # the file was not in the folder
            if not file_found:
                file_path = "www/404.html"
                file_size = os.path.getsize(file_path)
                content_len = "Content-Length: 1260\r\n"
                client.send(content_len.encode())
                file = open("www/404.html", "rb")
                data = file.read(chunk_size)
                client.send(data)
                file.close()
                if args.verbose:
                    logger.error("%s not found in %s", filename, args.folder)
                return

            # Get the size of the file
            file_path = args.folder + method[1]
            file_size = os.path.getsize(file_path)

            # Send back Content-Length
            content_len = "Content-Length: " + str(file_size) + "\r\n" + "\n"
            client.send(content_len.encode())

            if args.verbose:
                logger.info('Sending Data Back')
            file = open(file_path, "rb")
            chunk = file.read(chunk_size)
            while chunk:
                client.send(chunk)
                chunk = file.read(chunk_size)
                
            file.close()
            message = b''
            file_size = 0
        except ConnectionResetError:
            return
        except BrokenPipeError:
            return
        

################################################################################################################################################################
# Run server based on concurrency method
################################################################################################################################################################

# Initializing a Queue if thread-pool
thread_pool = []
tasks = queue.Queue()

def thread_worker(tasks):
    while True:
        client_conn = tasks.get()
        request_handler(client_conn)
        tasks.task_done()

if args.concurrency == 'thread-pool':
    for _ in range(10):
        thread = threading.Thread(target=thread_worker, args=(tasks,), daemon = True)
        thread_pool.append(thread)
        thread.start()


# Array for Threads
threads = []
if args.concurrency != 'thread-pool':
    try:
        while True:
            if args.verbose:
                logger.info("Server waiting for connection\n")

            # Connection created between given address
            conn, address = sock.accept()

            if args.verbose:
                logger.info("Connection established")

            while True:
                if args.concurrency == 'thread':
                    client_thread = threading.Thread(target = request_handler, args = (conn,))
                    threads.append(client_thread)
                    client_thread.start()
                    break
                    
                elif args.concurrency == 'single-thread':
                    request_handler(conn)
                    break       

            if args.verbose:
                logger.info("Closing socket\n")

    except KeyboardInterrupt:
        logger.info("Exiting Server\n")
        sock.close()
        sys.exit(0)
else:  
    try:
        while True:
            if args.verbose:
                logger.info("Server waiting for connection\n")

            conn, address = sock.accept()
            
            if args.verbose:
                logger.info("Connection established")

            tasks.put(conn)
    except KeyboardInterrupt:
        tasks.join()
        sock.close()
        sys.exit(0)
################################################################################################################################################################

