import logging
import random
import socket
import argparse
import socket
import struct
import time
import sys
import select


def randomize_text(text):
    def discard():
        return random.choices([True, False], weights=[1, 5])[0]

    def repeat(char):
        should_repeat = random.choices([True, False], weights=[1, 5])[0]

        if should_repeat:
            repeat_amount = int(random.paretovariate(1))
            return char * repeat_amount
        else:
            return char

    # text = text.decode()
    transformed_text = [repeat(c) for c in text if not discard()]

    if len(transformed_text) == 0:
        transformed_text = text[0]

    return "".join(transformed_text).encode()


def is_4_bytes(data):
    if isinstance(data, (bytes, bytearray)) and len(data) == 4:
        return True
    return False


PORT = 8083
HOST = ""
LEN_MASK = 0b00000111111111111111111111111111
ACT_MASK = 0b11111000000000000000000000000000
UPPERCASE = 0x01
LOWERCASE = 0x02
REVERSE = 0x04
SHUFFLE = 0x08
RANDOM = 0x10

# Parse the arguments
parser = argparse.ArgumentParser()
parser.add_argument(
    "-v", "--verbose", help="turn on debugging output", action="store_true"
)
parser.add_argument("-p", "--port", help="port to bind to", type=int, default=PORT)
args = parser.parse_args()

# Create a Socket
sock = socket.socket()
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((HOST, args.port))
sock.listen()

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

if args.verbose:
    logger.setLevel(logging.INFO)

# Receive/ Edit/ Send Responses
try:
    while True:
        conn, address = sock.accept()

        while True:
            if args.verbose:
                logger.info("Waiting for recv()")

            # Read in the header from the Socket if there is data to read in
            ready_to_read, _, _ = select.select([conn], [], [], 0.1)
            if conn in ready_to_read:
                header = conn.recv(4)
                if not header:
                    if args.verbose:
                        logger.info("Connection Closed")
                    break

            # Checks to see if we received all four bytes
            while True:
                if sys.getsizeof(header) >= 4:
                    break
                header_left = 4 - sys.getsizeof(header)
                header = header + conn.recv(header_left)

            # Decode the action and length
            newHead = struct.unpack("!i", header)
            length = newHead[0] & LEN_MASK
            action = (newHead[0] & ACT_MASK) >> 27

            # Checks to see if length was given
            if length <= 0:
                logger.error("Invalid length given")
                exit

            # Read in the message given the length of the message
            message = conn.recv(length)

            # Checks to see if we received the whole message
            while len(message) < length:
                message_left = length - len(message)
                if length == message_left:
                    logger.error("Error receiving full message")
                    break
                message = message + conn.recv(message_left)

            # Convert the message to a string
            message_str = message.decode("utf-8")

            if args.verbose:
                logger.info("Request Received")
                logger.info("Message: %s", message_str)

            # Rewrite the message based off of the action
            if action == UPPERCASE:
                message_str = message_str.upper()
                if args.verbose:
                    logger.info("Action: uppercase")

            elif action == LOWERCASE:
                message_str = message_str.lower()
                if args.verbose:
                    logger.info("Action: lowercase")

            elif action == REVERSE:
                message_str = message_str[::-1]
                if args.verbose:
                    logger.info("Action: reverse")

            elif action == SHUFFLE:
                message_shuffle = list(message_str)
                random.shuffle(message_shuffle)
                message_str = "".join(message_shuffle)
                if args.verbose:
                    logger.info("Action: shuffle")

            elif action == RANDOM:
                message_str = randomize_text(message_str)
                message_str = message_str.decode("utf-8")
                if args.verbose:
                    logger.info("Action: random")
            else:
                if args.verbose:
                    logger.error("Invalid Action")

            if args.verbose:
                logger.info("Response created")

            # Send the header + message back
            response_header = struct.pack("!I", len(message_str))
            full_response = response_header + message_str.encode()
            conn.send(full_response)

            if args.verbose:
                logger.info("Response sent: %s\n", full_response)

        # Close the Socket
        conn.close()

        if args.verbose:
            logger.info("Closing socket\n")


except KeyboardInterrupt:
    logger.info("Exiting Server\n")
    exit()


# def run(port):
#     server_socket = socket.socket()
#     server_socket.bind(("", port))
#     server_socket.listen()

#     while True:
#         conn, address = server_socket.accept()
#         logging.info(f"Connection from: {address}")

#         while True:
#             data = conn.recv(1024).decode()
#             logging.info(f"Received: {data}")

#             if not data:
#                 logging.info("Client disconnected...")
#                 break

#             conn.send(data.upper().encode())

#         conn.close()


# if __name__ == "__main__":
#     run(8083)
