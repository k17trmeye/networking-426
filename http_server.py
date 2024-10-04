import logging
import random
import socket
import argparse
import socket
import struct
import time
import sys
import select
import os

PORT = 8084
HOST = ""
FOLDER = "."

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
        check = "./" + folder
        if args.folder == check:
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

# Create a Socket
sock = socket.socket()
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((HOST, args.port))
sock.listen()
if args.verbose:
    logger.info("Socket Created")

# Receive/ Edit/ Send Responses
try:
    while True:
        if args.verbose:
            logger.info("Server waiting for connection\n")

        # Connection created between given address
        conn, address = sock.accept()

        if args.verbose:
            logger.info("Connection established")

        while True:
            if args.verbose:
                logger.info("Waiting for recv()")

            message = conn.recv(1024)

            if not message:
                if args.verbose:
                    logger.info("Connection Closed")
                break

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
                print("\n")

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
            conn.send(header_response.encode())

            # Making sure that the request is only GET
            if method[0] != "GET":
                file_path = "www/405.html"
                file_size = os.path.getsize(file_path)
                content_len = "Content-Length: " + str(file_size) + "\r\n"
                conn.send(content_len.encode())
                file = open(file_path, "rb")
                data = file.read(1024)
                conn.send(data)
                file.close()
                error_405 = "Content-Length: 0\r\n"
                if args.verbose:
                    logger.error(error_405)
                break

            if args.verbose:
                logger.info("GET Request")

            # If file_found flag wasn't set to true,
            # the file was not in the folder
            if not file_found:
                file_path = "www/404.html"
                file_size = os.path.getsize(file_path)
                content_len = "Content-Length: 1260\r\n"
                conn.send(content_len.encode())
                file = open("www/404.html", "rb")
                data = file.read(1024)
                conn.send(data)
                file.close()
                if args.verbose:
                    logger.error("%s not found in %s", filename, args.folder)
                break

            # Get the size of the file
            file_path = args.folder + method[1]
            file_size = os.path.getsize(file_path)

            # Send back Content-Length
            content_len = "Content-Length: " + str(file_size) + "\r\n" + "\n"
            conn.send(content_len.encode())

            # Chunk size (e.g., 1024 bytes)
            chunk_size = 1024

            with open(file_path, "rb") as file:
                while True:
                    chunk = file.read(chunk_size)
                    if not chunk:
                        break
                    conn.sendall(chunk)

            file.close()

        # Close the Socket
        conn.close()

        if args.verbose:
            logger.info("Closing socket\n")


except KeyboardInterrupt:
    logger.info("Exiting Server\n")
    exit()


# http://127.0.0.1:8085/background.jpg
