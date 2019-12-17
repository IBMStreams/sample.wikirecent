""""
Send video, frame-by-frame to Kafka interface
- Frame is encoded into ascii so no one gets upset with the data.
- Frame will be decomposed into chunks of 'CHUNK_SIZE'. When debugging found Kafka would not send message if it went over threshold.
- Receiving test notebook VideoRcvKafka

"""
import kafka
import os
import sys
import json
import base64
import ssl
import time
import datetime
import io
from PIL import Image
import logging
import cv2
import matplotlib.pyplot as plt
import numpy as np
if '../juypter' not in sys.path:
    sys.path.insert(0, '../juypter')
import credential

logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))
# img_encoded = str(base64.b64encode(response.content).decode("utf-8"))
# img_encoded = str(base64.b64encode(img).decode('utf-8'))


def bts_to_img(bts):
    buff = np.fromstring(bts, np.uint8)
    buff = buff.reshape(1, -1)
    img = cv2.imdecode(buff, cv2.IMREAD_COLOR)
    return img


def convertToRGB(image):
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def encode_img(img):
    """must be easier way"""
    with io.BytesIO() as output:
        img.save(output, format="JPEG")
        contents = output.getvalue()
    return base64.b64encode(contents).decode('ascii')


def decode_img(bin64):
    """must be easier way"""
    img = Image.open(io.BytesIO(base64.b64decode(bin64)))
    return img


CHUNK_SIZE = 100000         # maximum number of bytes to transmit at a time

def video_kafka(video_url, kafka_prod, kafka_topic='VideoFrame', frame_modulo=24, send_wait=.25, debug=False):
    """Send video via Kafka

    :param video_url: url of video to pull in and send
    :param kafka_prod: the handle to sent out messages on kafka
    :param frame_modulo: send every x frames
    :param send_wait: after sending a frame wait time
    :param debug: decode image and write out to verify
    :return: None

    """
    frame_num = 0

    cap = cv2.VideoCapture(video_url)
    while(cap.isOpened()):
        ret, frame = cap.read()
        if ret is False:
            break
        frame_num += 1
        if not(frame_num % frame_modulo):
            image_encoded =encode_img(Image.fromarray(frame, 'RGB'))
            if debug:
                # debugging - render what we will send.
                img_raw = decode_img(image_encoded)
                plt.imshow(img_raw)
                plt.show()
            # break down frame into chunks
            chunks = [image_encoded[i * CHUNK_SIZE:(i + 1) * CHUNK_SIZE] for i in
                      range((len(image_encoded) + CHUNK_SIZE - 1) // CHUNK_SIZE)]
            # send the chunks.
            for idx, chunk in enumerate(chunks):
                logging.debug("chunking - {}  #chunks :{} idx:{} len(chunk):{}".format(video_url, len(chunks), idx, len(chunk)))
                chunk_content = {'video': video_url,
                       'frame': frame_num,
                       'chunk_idx':idx,
                       'chunk_total':len(chunks),
                       'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
                       'data': chunk
                }
                kafka_prod.send(kafka_topic, value=json.dumps(chunk_content).encode('utf-8'))
            ## finish the frame frame
            chunk_complete = {'video': video_url,
                   'frame': frame_num,
                    'chunk_idx': len(chunks),
                    'chunk_total': len(chunks),
                   'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
                   'data': ""
                   }
            logging.info("frame's last chunk:{}".format(chunk_complete))
            kafka_prod.send(kafka_topic, value=json.dumps(chunk_complete).encode('utf-8'))
            time.sleep(send_wait)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    return


def kafka_producer(credentials):
    """
    Open the connection to the kafka producer
    :param credentials:
    :return: kafka producer

    Request is responsilbe for closing producer.
    """
    prod = None
    while prod is None:
        try:
            prod = kafka.KafkaProducer(bootstrap_servers=creds["kafka_brokers_sasl"],
                                       security_protocol="SASL_SSL",
                                       sasl_mechanism="PLAIN",
                                       sasl_plain_username=creds["user"],
                                       sasl_plain_password=creds["api_key"],
                                       ssl_cafile=ssl.get_default_verify_paths().cafile)

        except kafka.errors.NoBrokersAvailable:
            logging.warning("No Brokers Available. Retrying ...")
            time.sleep(1)
            prod = None
    return prod


"""
Selection of video use - 
 - Internet archive has many more.
"""
url = ['https://www.sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4',
'https://archive.org/download/popeye_shuteye_popeye/popeye_shuteye_popeye_512kb.mp4',
'https://archive.org/download/MuhammadAliVsSonnyListon/MuhammadAliVsSonnyListon_512kb.mp4',
'https://archive.org/download/bb_snow_white/bb_snow_white_512kb.mp4',
'https://archive.org/download/TuringTe2001/TuringTe2001_256kb.mp4',
'https://ia801309.us.archive.org/12/items/ISS-Tours/ISS-Tour_Flight-day-highlights_DI_2015_007_1256_220882.mp4',
'https://ia802705.us.archive.org/14/items/KarlFriedrichDraisTheBicycle/Karl%20Friedrich%20Drais%20The%20Bicycle.mp4'
]
SELECTED_VIDEO=3
TOPIC="VideoFrame"
if __name__ == '__main__':
    creds = json.loads(credential.magsEventStream)
    prod = kafka_producer(creds,)
    video_kafka(url[SELECTED_VIDEO], prod,  kafka_topic=TOPIC, frame_modulo=96)

    prod.close()
