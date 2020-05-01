"""stream_video support for streaming video


"""
import base64
import io
import logging
import ssl
import time
import collections


import cv2
import matplotlib.pyplot as plt
import numpy as np
import requests
from IPython.display import clear_output
from PIL import Image

import matplotlib.pyplot as plt
import ipywidgets as widgets
from ipywidgets import Button, HBox, VBox, Layout
from IPython.display import clear_output



def m3u8_segments(chunklist_text, base_path):
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
            segments.append({'secs': secs, 'segment': base_path + chunk})
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
    return out_ts



def extract_base(path):
    """extract the base path from path
    args:
        path : path the the chunk list
    return: the base path
    notes:
        - subsequnt processing needs the base path to build a URL to the videor data.
        - important that this results in the base to th server with the video data

    """
    split_url = path.split("/")
    base_path = "/".join(split_url[:-1]) + "/"
    return base_path


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


def show_frame(frame):
    image_encoded = encode_img(Image.fromarray(frame, 'RGB'))
    img_raw = decode_img(image_encoded)
    clear_output(wait=True)
    plt.imshow(img_raw)
    plt.show()


def fetch_frames(segment, frame_modulo=24, process_frame=show_frame):
    cap = cv2.VideoCapture(segment['segment'])
    count = 0
    frames = list()
    if (cap.isOpened()):
        ret, frame = cap.read()
        if ret is False:
            print("Failed to read frame....")
            return [frame]
        if count % frame_modulo == 0:
            frames.append(frame)
            process_frame(frame)
    else:
        print("Open failed....")
    return frames


def display_frame(segment) -> list:
    """Display 1 frame of the segment
    :return: list if images, one for now.

    - segment portion is a .ts file, read from the web.
    - A segment is composed of multiple frames.
    - Code can be modified to read multiple.

    """
    frame = None
    cap = cv2.VideoCapture(segment['segment'])
    if (cap.isOpened()):
        ret, frame = cap.read()
        if ret is False:
            print("Failed to read frame....")
            return [frame]
        image_encoded = encode_img(Image.fromarray(frame, 'RGB'))
        img_raw = decode_img(image_encoded)
        clear_output(wait=True)
        plt.imshow(img_raw)
        plt.show()
    else:
        print("Open failed....")
    return [frame]



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


def collect_frames(chunk_url, count=5):
    """collects frams making 'count' requests for chunks

    args:
        count : the number of chunks to fetch
    return:
        list of frames

    """
    cams_base = extract_base(chunk_url)
    collected_segment = collections.deque(maxlen=10)
    crop_frames = list()

    for idx in range(count):
        cams_response = requests.get(chunk_url)
        cams_chunklist = cams_response.text
        segments = m3u8_segments(cams_chunklist, cams_base)

        for segment in segments:
            # only get the first frame
            if segment not in collected_segment:
                frame = display_frame(segment)
                crop_frames.append(frame[0])
                #print("segment:", segment)
                collected_segment.append(segment)
            else:
                print("skip segment:", segment)
    return crop_frames



def crop_frame(frame, crop_specification):
    """crop a frame"""
    region_of_interest = (crop_specification.size[0],
                          crop_specification.size[1],
                          crop_specification.size[0] + crop_specification.size[2],
                          crop_specification.size[1] + crop_specification.size[3])
    orginal_encoded = encode_img(Image.fromarray(frame, 'RGB'))
    img_raw = decode_img(orginal_encoded)
    cropped = img_raw.crop(region_of_interest)
    image_encoded = encode_img(cropped)
    return image_encoded


def collected_frames(crop_frames, shape):
    """display a set of frame crops"""
    crop_label = widgets.Label(layout={'border': '1px solid green', 'width': '61%'})
    crop_widget = widgets.Output(layout={'border': '1px solid green', 'width': '61%', 'height': '270pt'})
    display(VBox([crop_label, crop_widget]))
    crop_label.value = "Review {} cropped images.".format(len(crop_frames))

    for idx in range(len(crop_frames)):
        with crop_widget:
            time.sleep(1)
            img = crop_frame(crop_frames[idx], shape)
            display(decode_img(img))
            crop_label.value = "{} of {}".format(idx + 1, len(crop_frames))
            clear_output(wait=True)


class image_select():
    """select a frame from a list of frames that are displayed.

    Note:
        - selected frame can used to define crop region.
        - must select the crop button to commit your frame selection
    """

    def __init__(self, crop_frames):
        """display selection of images, select one to be used fro crop definition """
        self.title_widget = widgets.Label(value="browse / select image to crop",
                                          layout={'border': '1px solid green', 'width': '61%'})
        self.image_widget = widgets.Output(layout={'border': '1px solid red', 'width': '61%', 'height': '270pt'})
        self.bck_button = widgets.Button(description="<", layout={'width': '20%'})
        self.crp_button = widgets.Button(description="crop", layout={'width': '20%'})
        self.fwd_button = widgets.Button(description=">", layout={'width': '20%'})
        self.crop_frames = crop_frames
        self.frame_idx = 0
        self.frame_selected_callback = None

    def display_image(self, image, image_widget):
        """convert from np array to image
           :param idx: index into frame

        """
        image_encoded = encode_img(Image.fromarray(image, 'RGB'))
        img_raw = decode_img(image_encoded)
        with image_widget:
            display(img_raw)
            clear_output(wait=True)

    def image_update(self, inc):
        if self.frame_idx + inc >= 0 and self.frame_idx + inc < len(self.crop_frames):
            self.frame_idx += inc
            self.title_widget.value = "Viewing image #{}".format(self.frame_idx)
            self.display_image(self.crop_frames[self.frame_idx], self.image_widget)

    def bckfwd_click(self, b):
        self.image_update(1 if b.description == '>' else -1)

    def crop_click(self, b):
        self.fwd_button.disabled = True
        self.bck_button.disabled = True
        self.frame_selected_callback(self.frame_idx)

    def ignition(self, frame_selected_callback):
        self.frame_selected_callback = frame_selected_callback
        self.crp_button.on_click(self.crop_click)
        self.fwd_button.on_click(self.bckfwd_click)
        self.bck_button.on_click(self.bckfwd_click)

        buttons = widgets.HBox([self.bck_button, self.crp_button, self.fwd_button])
        dashboard = widgets.VBox([self.title_widget, self.image_widget, buttons])
        display(dashboard)
        self.image_update(0)

