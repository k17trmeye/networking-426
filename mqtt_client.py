import logging
import random
import argparse
import socket
import struct
import time
import sys
import select
import os

PORT = 1883
HOST = 'localhost'
global message_received
message_received = False

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
parser.add_argument("-p", "--port", type=int, default=PORT)
parser.add_argument("-v", "--verbose", action="store_true")
parser.add_argument("--host", type=str, default = HOST)
parser.add_argument('netid', type=str)
parser.add_argument('action', type=str)
parser.add_argument('message', type=str)
args = parser.parse_args()

# Makes sure the action is a correct option
action_choices = ['uppercase', 'lowercase', 'reverse', 'shuffle', 'random']
action_valid = False
for action in action_choices:
    if args.action == action:
        action_valid = True

if action_valid == False:
    if args.verbose:
        logger.error('Invalid action: %s\n', args.action)
    sys.exit()

if args.verbose:
    logger.info('Port: %d', args.port)
    logger.info('Host: %s', args.host)
    logger.info('NetID: %s', args.netid)
    logger.info('Action: %s', args.action)
    logger.info('Message: %s\n', args.message)

import paho.mqtt.client as mqtt

# Defining callback functions
def on_connect(mqttc, obj, flags, rc):
    if rc == 0:
        if args.verbose:
            logger.info('Connected to MQTT Broker')
    else:
        if args.verbose:
            logger.error('Failed to Connect')


def on_message(mqttc, obj, msg):
    message = msg.payload.decode('utf-8')
    message_received = True
    print(message)


def on_publish(mqttc, obj, mid):
    if args.verbose:
        logger.info("mid: %s\n", str(mid))
    pass


def on_subscribe(mqttc, obj, mid, granted_qos):
    if args.verbose:
        logger.info("Subscribed: %s %s", str(mid), str(granted_qos))


def on_log(mqttc, obj, level, string):
    print(string)

# Set up MQTT Client
mqttc = mqtt.Client()
mqttc.on_message = on_message
mqttc.on_connect = on_connect
mqttc.on_publish = on_publish
mqttc.on_subscribe = on_subscribe

if args.verbose:
    logger.info('MQTT Client created')
    logger.info('Connecting to Broker')

# Connect to MQTT Broker
mqttc.connect(args.host, args.port)

# Start loop to handle messages and connections
mqttc.loop_start()

try:
    # Subscribe to the Broker
    request = args.netid + '/' + args.action + '/response'
    mqttc.subscribe(request, qos = 1)

    # Publish to Broker
    response = args.netid + '/' + args.action + '/request'
    infot = mqttc.publish(response, args.message, qos = 1)
    infot.wait_for_publish()
    
    while message_received:
        time.sleep(0.1)

except KeyboardInterrupt:
    logger.info('Closed by User')
finally:
    mqttc.loop_stop()  # Stop the MQTT client loop
    mqttc.disconnect()  # Disconnect the client
    sys.exit()
    
