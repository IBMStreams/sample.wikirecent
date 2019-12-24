import kafka
import os
import getpass
import sys
import json
import base64
import kafka
import ssl
import time
import datetime
import matplotlib.pyplot as plt
import io
from PIL import Image
import logging
if '../juypter' not in sys.path:
    sys.path.insert(0, '../juypter')
import credential


SSI_TOPIC = 'VideoFrame'
TEST_CAMERA_ID = "ImageTest-0"
count = 0



#creds_string = getpass.getpass()
creds = json.loads(credential.magsEventStream)

cons = kafka.KafkaConsumer(SSI_TOPIC,
                              bootstrap_servers=creds["kafka_brokers_sasl"],
                              security_protocol="SASL_SSL",
                              sasl_mechanism="PLAIN",
                                   sasl_plain_username=creds["user"],
                                   sasl_plain_password=creds["api_key"],
                                   ssl_cafile=ssl.get_default_verify_paths().cafile, consumer_timeout_ms=30000)

lst = []
start = time.time()
logging.getLogger("__name__").warning("start")
for msg in cons:
    print(msg)
    print(time.time())
print("done")

cons.close()
