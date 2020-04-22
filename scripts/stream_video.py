"""stream_video support for streaming video


"""


def m3u8_segments(chunklist_text, basePath):
    """Extract the segments (.ts) from chunk requests response.
       Expect to have a response with lines
       ```
          #EXTINF:<secs>
          <filename>.ts
             :
             :
        ```
    args:
        chunklist_response : requests .text results.
        basePath : path (no file name) to the media server
    """
    chunk_desc = [ele for ele in chunklist_text.split("\n")[:-1]]
    segments = []
    secs = -1
    for chunk in chunk_desc:
        if chunk.startswith("#EXTINF:"):
            split = chunk.split(":")
            secs = float(split[1][:-1])
        elif chunk[0] != "#":
            segments.append({'secs': secs, 'segment': basePath + chunk})
    return segments


def collect_segments(out_ts, segments):
    """collect all the segments from the remote side write inot file
    args:
        segments : [{url, secs}, ...] -
        out_ts : file name where all segment are to be concatenated into.

    """
    with open(out_ts, "wb") as f:
        for ele in segments:
            print("get segment:", ele)
            r = requests.get(ele['segment'])
            f.write(r.content)
    return (out_ts)


def extract_base(path):
    """extract the base path from path
    args:
        path : path the the chunk list
    retur: the base path
    notes:
        - subsequnt processing needs the base path to build a URL to the videor data.
        - important that this results in the base to th server with the video data

    """
    split_url = path.split("/")
    base_path = "/".join(split_url[:-1]) + "/"
    return base_path

import requests
import urllib
import m3u8
from urllib.parse import urlparse
import re
import string
import cv2

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
from IPython.display import clear_output
import numpy as np


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


def display_frame(segment):
    """Display 1 frame of the segment
       Args:
           segment frames to be rendered
       Notes:
            - segment portion is a .ts file, read from the web.
            - A segment is composed of multiple frames.
       - Code can be modified to read multiple.


    t"""
    cap = cv2.VideoCapture(segment['segment'])
    if (cap.isOpened()):
        ret, frame = cap.read()
        if ret is False:
            print("Failed to read frame....")
            return
        image_encoded = encode_img(Image.fromarray(frame, 'RGB'))
        img_raw = decode_img(image_encoded)
        clear_output(wait=True)
        plt.imshow(img_raw)
        plt.show()
    else:
        print("Open failed....")


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
            prod = kafka.KafkaProducer(bootstrap_servers=credentials["kafka_brokers_sasl"],
                                       security_protocol="SASL_SSL",
                                       sasl_mechanism="PLAIN",
                                       sasl_plain_username=credentials["user"],
                                       sasl_plain_password=credentials["api_key"],
                                       ssl_cafile=ssl.get_default_verify_paths().cafile)

        except kafka.errors.NoBrokersAvailable:
            logging.warning("No Brokers Available. Retrying ...")
            time.sleep(1)
            prod = None
    return prod
