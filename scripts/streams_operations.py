import base64
import collections
import csv
import io
from urllib.parse import urlparse

import requests
import streamsx.rest as rest
#from PIL import Image
from bs4 import BeautifulSoup
from sseclient import SSEClient as EventSource
from streamsx.topology import context
from streamsx.topology.topology import *


def get_instance(service_name="Steaming3Turbine"):
    """Setup to access your Streams instance.

    ..note::The notebook is work within Cloud and ICP4D.
            Refer to the 'Setup' cells above.
    Returns:
        instance : Access to Streams instance, used for submitting and rendering views.
    """
    try:
        from icpd_core import icpd_util
        import urllib3
        global cfg
        cfg[context.ConfigParams.SSL_VERIFY] = False
        instance = rest.Instance.of_service(cfg)
        print("Within ICP4D")
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except ImportError:
        cfg = None
        print("Outside ICP4D")
        import credential
        sc = rest.StreamingAnalyticsConnection(service_name='Streaming3Turbine',
                                               vcap_services=credential.vcap_conf)
        instance = sc.get_instances()[0]
    return instance,cfg



def get_events():
    """fetch recent changes from wikievents site using SSE"""
    for change in EventSource('https://stream.wikimedia.org/v2/stream/recentchange'):
        if len(change.data):
            try:
                obj = json.loads(change.data)
            except json.JSONDecodeError as err:
                print("JSON l1 error:", err, "Invalid JSON:", change.data)
            except json.decoder.JSONDecodeError as err:
                print("JSON l2 error:", err, "Invalid JSON:", change.data)
            else:
                yield (obj)


class sum_aggregation():
    def __init__(self, sum_map={'new_len': 'newSum', 'old_len': 'oldSum', 'delta_len': 'deltaSum'}):
        """
        Summation of column(s) over a window's tuples.
        Args::
            sum_map :  specfify tuple columns to be summed and the result field.
            tuples : at run time, list of tuples will flow in. Sum each fields
        """
        self.sum_map = sum_map

    def __call__(self, tuples) -> dict:
        """
        Args:
            tuples : list of tuples constituting a window, over all the tuples sum using the sum_map key/value
                     to specify the input and result field.
        Returns:
            dictionary of fields summations over tuples

        """
        summaries = dict()
        for summary_field, result_field in self.sum_map.items():
            summation = sum([ele[summary_field] for ele in tuples])
            summaries.update({result_field: summation})
        return (summaries)



class tally_fields(object):
    def __init__(self, top_count=3, fields=['user', 'wiki', 'title']):
        """
        Tally fields of a list of tuples.
        Args::
            fields :  fields of tuples that are to be tallied
        """
        self.fields = fields
        self.top_count = top_count

    def __call__(self, tuples) -> dict:
        """
        Args::
            tuples : list of tuples tallying to perform.
        return::
            dict of tallies
        """
        tallies = dict()
        for field in self.fields:
            stage = [tuple[field] for tuple in tuples if tuple[field] is not None]
            tallies[field] = collections.Counter(stage).most_common(self.top_count)
        return tallies




class wiki_lang():
    """
    Augment the tuple to include language wiki event.

    Mapping is loaded at build time and utilized at runtime.
    """

    def __init__(self, fname="wikimap.csv"):
        self.wiki_map = dict()
        with open(fname, mode='r') as csv_file:
            csv_reader = csv.DictReader(csv_file)
            for row in csv_reader:
                self.wiki_map[row['dbname']] = row

    def __call__(self, tuple):
        """using 'wiki' field to look pages code, langauge and native
        Args:
            tuple: tuple (dict) with a 'wiki' fields
        Returns:'
            input tuple with  'code', 'language, 'native' fields added to the input tuple.
        """
        if tuple['wiki'] in self.wiki_map:
            key = tuple['wiki']
            tuple['code'] = self.wiki_map[key]['code']
            tuple['language'] = self.wiki_map[key]['in_english']
            tuple['native'] = self.wiki_map[key]['name_language']
        else:
            tuple['code'] = tuple['language'] = tuple['native'] = None
        return tuple


# @lru_cache(maxsize=None)
def shred_item_image(url):
    """Shred the item page, seeking image.

    Discover if referencing image by shredding referening url. If it is, dig deeper
    and extract the 'src' link.

    Locate the image within the page, locate <a class='image' src=**url** ,..>

    This traverses two files, pulls the thumbnail ref and follows to fullsize.

    Args:
        url: item page to analyse

    Returns:
        If image found [{name,title,org_url},...]

    .. warning:: this fetches from wikipedia, requesting too frequenty is bad manners. Uses the lru_cache()
    so it minimises the requests.

    This can pick up multiple titles, on a page that is extract, dropping to only one.
    """
    img_urls = list()
    try:
        rThumb = requests.get(url=url)
        # print(r.content)
        soupThumb = BeautifulSoup(rThumb.content, "html.parser")
        divThumb = soupThumb.find("div", class_="thumb")
        if divThumb is None:
            print("No thumb found", url)
            return img_urls
        thumbA = divThumb.find("a", class_="image")
        thumbHref = thumbA.attrs['href']

        rFullImage = requests.get(url=thumbHref)
        soupFull = BeautifulSoup(rFullImage.content, "html.parser")
    except Exception as e:
        print("Error request.get, url: {} except:{}".format(url, str(e)))
    else:
        divFull = soupFull.find("div", class_="fullImageLink", id="file")
        if (divFull is not None):
            fullA = divFull.find("a")
            img_urls.append({"title": soupThumb.title.getText(), "img": fullA.attrs['href'], "org_url": url})
    finally:
        return img_urls


# @lru_cache(maxsize=None)
def shred_jpg_image(url):
    """Shed the jpg page, seeking image, the reference begins with 'Fred:' and
    ends with '.jpg'.

    Discover if referencing image by shredding referening url. If it is, dig deeper
    and extract the 'src' link.

    Locate the image within the page,
            locate : <div class='fullImageLinks'..>
                         <a href="..url to image" ...>.</a>
                         :
                     </div>
    Args:
        url: item page to analyse

    Returns:
        If image found [{name,title,org_url='requesting url'},...]

    .. warning:: this fetches from wikipedia, requesting too frequenty is bad manners. Uses the lru_cache()
    so it minimises the requests.

    """
    img_urls = list()
    try:
        r = requests.get(url=url)
        soup = BeautifulSoup(r.content, "html.parser")
    except Exception as e:
        print("Error request.get, url: {} except:{}".format(url, str(e)))
    else:
        div = soup.find("div", class_="fullImageLink")
        if (div is not None):
            imgA = div.find("a")
            img_urls.append({"title": soup.title.getText(), "img": "https:" + imgA.attrs['href'], "org_url": url})
        else:
            print("failed to find div for", url)
    finally:
        return img_urls


class soup_image_extract():
    """If the the field_name has a potential a image we

    Return:
        None : field did not have potenital for an image.
        [] : had potential but no url found.
        [{title,img,href}]
    """

    def __init__(self, field_name="title", url_base="https://www.wikidata.org/wiki/"):
        self.url_base = url_base
        self.field_name = field_name

    def __call__(self, _tuple):
        title = _tuple[self.field_name]
        img_desc = None
        if (title[0] == "Q"):
            lnk = self.url_base + title
            img_desc = shred_item_image(lnk)
        elif title.startswith("File:") and (title.endswith('.JPG') or title.endswith('.jpg')):
            lnk = self.url_base + title.replace(' ', '_')
            img_desc = shred_jpg_image(lnk)
        _tuple['img_desc'] = img_desc
        return _tuple


class soup_image():
    """If the the field_name has a potential for a image we

    Return:
        None : field did not have potenital for an image.
        [] : had potential but no url found.
        [{title,img,href}]
    """

    def __init__(self, field_name="title", url_base="https://www.wikidata.org/wiki/"):
        self.url_base = url_base
        self.field_name = field_name
        self.cache_item = None
        self.cache_jpg = None

    def __call__(self, _tuple):
        if self.cache_item is None:
            self.cache_item = cache_url_process(shred_item_image)
            self.cache_jpg = cache_url_process(shred_jpg_image)
        title = _tuple[self.field_name]
        img_desc = None
        if (title[0] == "Q"):
            lnk = self.url_base + title
            img_desc = self.cache_item.cache_process(lnk)
            print("cache_item", self.cache_item.stats())

        elif title.startswith("File:") and (title.endswith('.JPG') or title.endswith('.jpg')):
            lnk = self.url_base + title.replace(' ', '_')
            img_desc = self.cache_jpg.cache_process(lnk)
            print("cache_jpg", self.cache_jpg.stats())

            # print("cache_jpg", self.cache_jpg.stats())

        _tuple['img_desc'] = img_desc
        return _tuple


## Support of streams processing
class cache_url_process():
    def __init__(self, process_url, cache_max=200):
        """I would use @lru_cache() but I ran into two problems.
           - when I got to the server it could not find the function.
           - get a stack overflow when building the topology.
        Args::
            process_url: a function that process's the request, when not cached.
            Function will accept a URL and retrn  dict.
        Return::
            result from process_url that may be a cached value.

        """
        self.urls = collections.OrderedDict()
        self.hits = 0
        self.attempts = 0
        self.process = process_url
        self.cache_max = cache_max

    def cache_process(self, url):
        self.attempts += 1
        if url in self.urls:
            self.hits += 1
            stage = self.urls[url]
            del self.urls[url]  # move to begining of que
            self.urls[url] = stage
            n = len(self.urls) - self.cache_max
            [self.urls.popitem(last=False) for idx in range(n if n > 0 else 0)]
            return stage
        stage = self.process(url)
        self.urls[url] = stage
        return stage

    def stats(self):
        return dict({"attempts": self.attempts, "hits": self.hits, "len": len(self.urls)})

"""
Facial Exaction.....
"""


tmpBufIoOut = None

def facial_fetch(imgurl):
    """Using the facial recognizer get the location of all the faces on the image.

    Args:
        imgurl : image the recognizer is done on.
    Return:
        location of found faces
    ..note:
        - In light of the fact that were using a free service, it can stop working at anytime.
        - Pulls the binary image from wikipedia forwards the binary onto the service.
    """
    predict_url = 'http://max-facial-recognizer.max.us-south.containers.appdomain.cloud/model/predict'
    parsed = urlparse(imgurl)
    filename = parsed.path.split('/')[-1]
    if (filename.lower().endswith('.svg')):
        print("Cannot process svg:", imgurl)
        return list(), None
    if (filename.lower().endswith('.tif')):
        print("Cannot process tif:", imgurl)
        return list(), None
    try:
        page = requests.get(imgurl)
    except Exception as e:
        print("Image fetch exception:", e)
        return None, None
    bufIoOut = io.BytesIO(page.content)
    files = {'image': (filename, bufIoOut, "image/jpeg")}
    try:
        r = requests.post(predict_url, files=files)
    except Exception as e:
        print("Analysis service exception", e)
        return None, None
    if (r.status_code != 200):
        print("Analysis failure:", r.status_code, r.json())
        return None, None
    analysis = r.json()
    return analysis, bufIoOut


def facial_locate(imgurl):
    analysis, bufIoOut = facial_fetch(imgurl)
    if bufIoOut is None:
        return None
    if (analysis['predictions']) == 0:
        print("No predictions found for", imgurl)
        return None
    return ({'bin_image': bufIoOut, 'faces': analysis})


def crop_percent(img_dim, box_extent):
    """get the % of image the cropped image is"""
    img_size = img_dim[0] * img_dim[1]
    box_size = abs((int(box_extent[0]) - int(box_extent[2])) * (int(box_extent[1]) - int(box_extent[3])))
    percent = ((box_size / img_size) * 100)
    return (percent)


def image_cropper(bin_image, faces):
    """Crop out the faces from a URL.
    Args:
        url : image images
        faces : list of {region,predictions} that that should be cropped
    Return:
        dict with 'annotated_image' and 'crops'
        'crops' is list of dicts with
            {image:face image,
             probability:chances it's a face,
             image_percent:found reqion % of of the image,
             detection_box:region of the original image that the image was extacted from}
         'crops' empty - nothing found, no faces found
    """
    crops = list()
    for face in faces['predictions']:
        i = Image.open(bin_image)
        percent = crop_percent(i.size, face['detection_box'])
        img = i.crop(face['detection_box'])
        crops.append({'image': img, 'probability': face['probability'], 'detection_box': face['detection_box'],
                      'image_percent': percent})
    return crops


class facial_image():
    """Extract all the faces from an image, for each found face generate a tuple with a face field.
    Args:
        - field_name : name of field on input tuple with the image description dict
        - img_field : dictionary entry that has url of image


    Return:
        None - No 'img_desc' field or no faces found
        List of tuples composed of the input tuple with a new 'face' field
        face a dictionary:
        - probability : probability that it's a face
        - percentage : % of the field_img that the detection_box occupies
        - detection_box : within the orginal image, coodinates of extracted image
        - bytes_PIL_b64 : cropped image in binary Base64 ascii
    ..notes:
        1. the next operator in line should be the flat_map() that takes the list of tuples and converts
        to a stream of tuples.
    ..code::
        '''
        ## Example of displaying encoded cropped image.
        from PIL import Image
        from io import BytesIO
        import copy

        calidUrlImage = "URL of valid Image to be analysized"
        minimal_tuple = {'img_desc':[{'img':validUrlImage}]}
        fi = facial_image()
        crops = fi.__call__(minimal_tuple)
        for crop in crops:
            cropImg = Image.open(io.BytesIO(base64.b64decode(crop['face']['bytes_PIL_b64'])))
            print("Image Size",cropImg.size)
            display(cropImg)
        '''
    """

    def __init__(self, field_name="img_desc", url_base="https://www.wikidata.org/wiki/", image_field='img'):
        self.url_base = url_base
        self.img_desc = field_name
        self.img_field = image_field
        self.cache_item = None

    def __call__(self, _tuple):

        if self.img_desc not in _tuple or len(_tuple[self.img_desc]) == 0:
            return None
        desc = _tuple[self.img_desc][0]
        if self.img_field not in desc:
            print("Missing 'img' field in 'img_desc'")
            return None
        processed = facial_locate(desc[self.img_field])
        if processed is None:
            return None

        crops = image_cropper(processed['bin_image'], processed['faces'])
        tuples = list()
        for crop in crops:
            augmented_tuple = copy.copy(_tuple)
            with io.BytesIO() as output:
                crop['image'].save(output, format="JPEG")
                contents = output.getvalue()
            crop['bytes_PIL_b64'] = base64.b64encode(contents).decode('ascii')
            del crop['image']
            augmented_tuple['face'] = crop
            tuples.append(augmented_tuple)
        return tuples

"""
Emotion Extraction...
"""


def emotion_crop(bufIoOut, imgurl):
    """ Our friends: "https://developer.ibm.com/exchanges/models/all/max-facial-emotion-classifier/"

    Analyse an image using the service "http://max-facial-emotion-classifier.max.us-south.containers.appdomain.cloud/".

    Send binary image to analysis

    The processing nodes not necessarily return a prediction, could be an indication that it's not a predictable image.

    Args:
        imgurl: the original source image that the cropped region came from
        bufIoOut : the binary cropped image to be analysized

    Returns:
        None - error encountered
        [] : executed, no prediction.
        [{anger,contempt,disgust,happiness,neutral,sadness,surpise}]
    ..note:
        This utilizing a function put up the by our friends, $$ == 0.
        It can stop working at anytime.
    """
    predict_url = 'http://max-facial-emotion-classifier.max.us-south.containers.appdomain.cloud/model/predict'
    parsed = urlparse(imgurl)
    filename = parsed.path.split('/')[-1]

    files = {'image': (filename, bufIoOut, "image/jpeg")}
    try:
        r = requests.post(predict_url, files=files)
    except Exception as e:
        print("Analysis service exception", e)
        return None
    if (r.status_code != 200):
        print("Analysis failure:", r.status_code, r.json())
        return None
    analysis = r.json()
    if len(analysis['predictions']) == 0:
        return list()
    emotions = analysis['predictions'][0]['emotion_predictions']
    return [{emot['label']: float("{0:.2f}".format(emot['probability'])) for emot in emotions}]


class emotion_image():
    """If there is an img entry, attempt to analyize
    Args:
        field_name : name of field on input tuple with the image description dict
        img_field: dictionary entry that has url of image

    Return:
        None - No 'img_desc' field or no entries in the field
        Add a emotion to the tuple.
            Empty [] if nothing in img_desc or no emotion could be derived
            None : field did not have potenital for an image.
        [] : had potential but no url found.
        [{title,img,href}]
    """

    def __init__(self):
        pass

    def __call__(self, _tuple):
        bufIoOut_decode_image = io.BytesIO(base64.b64decode(_tuple['face']['bytes_PIL_b64']))
        url = _tuple['img_desc'][0]['img']
        emotion = emotion_crop(bufIoOut_decode_image, url)
        _tuple['emotion'] = emotion
        return (_tuple)