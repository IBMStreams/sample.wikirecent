import numpy as np
import requests
from streamsx.topology.topology import *
import io
import base64
from cv2 import IMREAD_COLOR
from cv2 import COLOR_BGR2RGB
from cv2 import CascadeClassifier
from cv2 import imdecode
from cv2 import cvtColor
import logging

"""
  OpenCv support for Streams Image processing....

"""

logging.getLogger("cvsupport")

class ImageFetch:
    def __init__(self):
        """ Fetch image using the url using  'img_desc'][0]['img'] of the tuple. 
    
        Return: 
          Success : input tuple witn additional field 'img_string' the image encoded as a string.

        ```Python
        decode_img(tuple.img_string) # retrieve the image
        ```
        """
        pass
    def __exit__(self, exception_type, exception_value, traceback):
        logging.getLogger(__name__).error("*EXIT invoked type:{} value:{}".format(exception_type, exception_value))
        True
    
    def __call__(self, _tuple):
        img_url = _tuple['img_desc'][0]['img']
        response = requests.get(img_url)
        _tuple['img_string'] = str(base64.b64encode(response.content).decode("utf-8"))
        return _tuple


class FaceRegions:
    def __init__(self, haar_file=None):
        """ Find faces in image using img_string of tuple. 
          Return: tuple augmented with 'face_regions', a list of face_regions.
        """
        self.haar_cascade_face = None
        self.haar_file = haar_file
    def __enter__(self):
        if self.haar_file is None:
            self.haar_file = streamsx.ec.get_application_directory() + "/etc/haarcascade_frontalface_default.xml"
        if self.haar_cascade_face is None:
            self.haar_cascade_face = CascadeClassifier(self.haar_file)

    
    def __exit__(self, exception_type, exception_value, traceback):
        logging.getLogger(__name__).error("*EXIT invoked type:{} value:{}".format(exception_type, exception_value))
        True
        
    def bts_to_img(self, bts):
        buff = np.fromstring(bts, np.uint8)
        buff = buff.reshape(1, -1)
        img = imdecode(buff, IMREAD_COLOR)
        return img
        
    def convertToRGB(self, image):
        return cvtColor(image, COLOR_BGR2RGB)
      
    def __call__(self, _tuple):
        if self.haar_file is None:
            self.haar_file = streamsx.ec.get_application_directory() + "/etc/haarcascade_frontalface_default.xml"
        if self.haar_cascade_face is None:
            self.haar_cascade_face = CascadeClassifier(self.haar_file)
        bio = io.BytesIO(base64.b64decode(_tuple['img_string']))
        img_raw = self.bts_to_img(bio.read())
        if img_raw is None:
            print("img_url:{} bts_img() failed".format(img_url))
            return None
        print("Size of image to process : ",img_raw.shape)
        img_rgb = self.convertToRGB(img_raw)
        face_rects = self.haar_cascade_face.detectMultiScale(img_rgb, scaleFactor = 1.2, minNeighbors = 5)
        _tuple['face_regions'] = face_rects
        return _tuple