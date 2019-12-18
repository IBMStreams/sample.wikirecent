import numpy as np
import requests
from streamsx.topology.topology import *
import streamsx
import io
import base64

import cv2
from cv2 import IMREAD_COLOR
from cv2 import COLOR_BGR2RGB
from cv2 import CascadeClassifier
from cv2 import imdecode
from cv2 import cvtColor
from PIL import Image

import logging

"""
  OpenCv support for Streams Image processing....

"""

logging.getLogger("cvsupport")


class ImageFetch:
    """
    Fetch image using URL of tuple..
    """

    def __init__(self):
        """ Fetch image .

        Notes:

            * decode_img(tuple.image_string) # to return encoded string as an image.
        ```
        """
        pass

    def __exit__(self, exception_type, exception_value, traceback):
        logging.getLogger(__name__).error("*EXIT invoked type:{} value:{}".format(exception_type, exception_value))
        return True  # do not re-raise the exception.

    def __call__(self, _tuple):
        """ The processing

        Args:
            _tuple: field 'img_desc'][0]['img'] has image url to be fetched

        Returns:
            'image_string', image encoded as a string added to _tuple, None on failure
        """

        img_url = _tuple['img_desc'][0]['img']
        response = requests.get(img_url)
        if not response.ok:
            logging.getLogger(__name__).warning("Error {} on url:{}".format(response, img_url))
            return None
        _tuple['source'] = 'img_url'
        _tuple['image_string'] = str(base64.b64encode(response.content).decode("utf-8"))
        return _tuple


class FaceRegions:
    """ Find faces in image using image_string of tuple.

    """

    def __init__(self, haar_file=None):
        self.haar_cascade_face = None
        self.haar_file = haar_file

    def __enter__(self):
        if self.haar_file is None:
            self.haar_file = streamsx.ec.get_application_directory() + "/etc/haarcascade_frontalface_default.xml"
        if self.haar_cascade_face is None:
            self.haar_cascade_face = CascadeClassifier(self.haar_file)
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        logging.getLogger(__name__).error("*EXIT invoked type:{} value:{}".format(exception_type, exception_value))
        return True  # do not re-raise the exception.

    def bts_to_img(self, bts):
        buff = np.fromstring(bts, np.uint8)
        buff = buff.reshape(1, -1)
        img = imdecode(buff, IMREAD_COLOR)
        return img

    def convertToRGB(self, image):
        return cvtColor(image, COLOR_BGR2RGB)

    def __call__(self, _tuple):
        """ The processing

        Args:
            _tuple: process the image_string f9eld

        Returns:
            faces_regions added to tuple None on failure
        """
        if self.haar_file is None:
            self.haar_file = streamsx.ec.get_application_directory() + "/etc/haarcascade_frontalface_default.xml"
        if self.haar_cascade_face is None:
            self.haar_cascade_face = CascadeClassifier(self.haar_file)

        bio = io.BytesIO(base64.b64decode(_tuple['image_string']))
        img_raw = self.bts_to_img(bio.read())
        if img_raw is None:
            img_url = _tuple['img_desc'][0]['img']
            logging.getLogger(__name__).warning("Fail bts_to_img() on url: {}".format(img_url))
            return None
        print("Size of image to process : ", img_raw.shape)
        img_rgb = self.convertToRGB(img_raw)
        face_rects = self.haar_cascade_face.detectMultiScale(img_rgb, scaleFactor=1.2, minNeighbors=5)
        if len(face_rects) is 0:
            return None
        _tuple['face_regions'] = face_rects.tolist()
        return _tuple


class ObjectRegions:

    def __init__(self, classes="None", weights="/etc/yolov3.weights", config="/etc/yolov3.cfg", on_streams=True):
        """Locate objects(s) in and image, item and location.
        :param classes: classes of objects, loaded locally
        :param weights:
        :param config:
        :param on_streams : function is to be invoked within streams application
        """
        with open(classes, 'r') as f:
            self.classes = [line.strip() for line in f.readlines()]
        self.weights = weights
        self.config = config
        self.COLORS = np.random.uniform(0, 255, size=(len(self.classes), 3))
        self.scale = 0.00392
        self.conf_threshold = 0.8
        self.nms_threshold = 0.4
        self.on_streams = on_streams

    def __enter__(self):
        if self.on_streams:
            self.weights = streamsx.ec.get_application_directory() + self.weights
            self.config = streamsx.ec.get_application_directory() + self.config
        self.net = cv2.dnn.readNet(self.weights, self.config)
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        logging.getLogger(__name__).error("*EXIT invoked type:{} value:{}".format(exception_type, exception_value))
        return True  # do not re-raise the exception....

    def bts_to_img(self, bts):
        buff = np.fromstring(bts, np.uint8)
        buff = buff.reshape(1, -1)
        img = imdecode(buff, IMREAD_COLOR)
        return img

    def convertToRGB(self, image):
        return cvtColor(image, COLOR_BGR2RGB)

    def __call__(self, _tuple):
        """"
        Note:
            - output results must be json compliant

        """
        bio = io.BytesIO(base64.b64decode(_tuple['image_string']))
        img_raw = self.bts_to_img(bio.read())
        # def yolo_detect(frame,conf_threshold):
        blob = cv2.dnn.blobFromImage(img_raw, self.scale, (416, 416), (0, 0, 0), True, crop=False)
        self.net.setInput(blob)
        layer_names = self.net.getLayerNames()
        output_layers = [layer_names[i[0] - 1] for i in self.net.getUnconnectedOutLayers()]
        outs = self.net.forward(output_layers)

        class_ids = []
        confidences = []
        boxes = []

        for out in outs:
            for detection in out:
                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]
                if confidence > self.conf_threshold:
                    final_h, final_w = img_raw.shape[:2]
                    box = detection[0:4] * np.array([final_w, final_h, final_w, final_h])
                    (centerX, centerY, newWidth, newHeight) = box.astype("int")
                    x = centerX - newWidth / 2
                    y = centerY - newHeight / 2
                    class_ids.append(class_id)
                    confidences.append(float(confidence))
                    boxes.append([float(x), float(y), float(newWidth), float(newHeight)])

        if len(class_ids) == 0:
            return None
        regions = [{"class": self.classes[class_ids[idx]], "confidence": confidences[idx], "region": boxes[idx]} for idx
                   in range(len(class_ids))]
        _tuple['object_regions'] = regions
        return (_tuple)


class BuildVideoFrame:
    def __init__(self):
        """Image frames come across in chunks the put the chunks back together """

    def decode_img(image_string):
        """ convert an string to image"""
        img = Image.open(io.BytesIO(base64.b64decode(image_string)))
        return img

    def __enter__(self):
        self.startup = True
        self.image_string = ""

    def __exit__(self, exception_type, exception_value, traceback):
        logging.getLogger(__name__).error("* EXIT invoked type:{} value:{}".format(exception_type, exception_value))
        return True   # do not re-raise the exception

    def __call__(self, chunk):
        """When starting need to synchronize to the beginning of the chunk.
           Subsequently, rely on the Kafka to delivery messages order, which may be naive;
           their is a enough data in the message to build image correctly.
        """
        # chunk = json.loads(msg[6])
        if self.startup:
            if chunk['chunk_idx'] != 0:
                self.startup = False

        if chunk['chunk_idx'] == 0:
            # start of a new frame.
            self.image_string = chunk['data']
            return None

        if chunk['chunk_idx'] == chunk['chunk_total']:
            # frame complete - build tuple, with image_string return
            # image = self.decode_img(self.image_string)
            img = "{}@{}".format(chunk['video'],chunk['frame'])
            img_desc = [{'img':img, 'video':chunk['video'], 'frame':chunk['frame']}]
            tuple = {'source':'kafka', 'image_string': self.image_string, 'img_desc':img_desc, 'timestamp': chunk['timestamp']}
            self.image_string = ""
            return tuple

        # building up frame
        self.image_string = "".join([self.image_string, chunk['data']])
        return None
