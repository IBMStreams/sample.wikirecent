"""
Collection of functions to assist in rendering of the view data in Notebook.

"""

import base64
import io
import time
import threading
from PIL import Image,  ImageDraw  # https://pillow.readthedocs.io/en/4.3.x/
import requests  # http://docs.python-requests.org/en/master/

import ipywidgets as widgets
import matplotlib.pyplot as plt
from IPython.display import display, clear_output
from ipywidgets import HBox, Layout

# TODO move to streams_aid
def catchInterrupt(func):
    """decorator : when interupt occurs the display is lost if you don't catch it
       TODO * <view>.stop_data_fetch()  # stop

    """

    def catch_interrupt(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except (KeyboardInterrupt):
            pass

    return catch_interrupt


# TODO move to streams_aid
# Support for locating/rendering views.
def display_view_stop(eventView, period=2):
    """Wrapper for streamsx.rest_primitives.View.display() to have button. """
    button = widgets.Button(description="Stop Updating")
    display(button)
    eventView.display(period=period)

    def on_button_clicked(b):
        eventView.stop_data_fetch()
        b.description = "Stopped"

    button.on_click(on_button_clicked)

# TODO move to streams_aid
def view_events(views):
    """
    Build interface to display a list of views and
    display view when selected from list.

    """
    view_names = [view.name for view in views]
    nameView = dict(zip(view_names, views))
    select = widgets.RadioButtons(
        options=view_names,
        value=None,
        description='Select view to display',
        disabled=False
    )

    def on_change(b):
        if (b['name'] == 'label'):
            clear_output(wait=True)
            [view.stop_data_fetch() for view in views]
            display(select)
            display_view_stop(nameView[b['new']], period=2)

    select.observe(on_change)
    display(select)


# TODO move to streams_aid
def find_job(instance, job_name=None):
    """locate job within instance"""
    for job in instance.get_jobs():
        if job.applicationName.split("::")[-1] == job_name:
            return job
    else:
        return None

# TODO move to streams_aid
def display_views(instance, job_name):
    """Locate/promote and display all views of a job"""
    job = find_job(instance, job_name=job_name)
    if job is None:
        print("Failed to locate job")
    else:
        views = job.get_views()
        view_events(views)

# TODO move to streams_aid
def list_jobs(_instance=None, cancel=False):
    """
    Interactive selection of jobs to cancel.

    Prompts with SelectMultiple widget, if thier are no jobs, your presente with a blank list.

    """
    active_jobs = {"{}:{}".format(job.name, job.health): job for job in _instance.get_jobs()}

    selectMultiple_jobs = widgets.SelectMultiple(
        options=active_jobs.keys(),
        value=[],
        rows=len(active_jobs),
        description="Cancel jobs(s)" if cancel else "Active job(s):",
        layout=Layout(width='60%')
    )
    cancel_jobs = widgets.ToggleButton(
        value=False,
        description='Cancel',
        disabled=False,
        button_style='warning',  # 'success', 'info', 'warning', 'danger' or ''
        tooltip='Delete selected jobs',
        icon="stop"
    )

    def on_value_change(change):
        for job in selectMultiple_jobs.value:
            print("canceling job:", job, active_jobs[job].cancel())
        cancel_jobs.disabled = True
        selectMultiple_jobs.disabled = True

    cancel_jobs.observe(on_value_change, names='value')
    if cancel:
        return HBox([selectMultiple_jobs, cancel_jobs])
    else:
        return HBox([selectMultiple_jobs])


def render_image(image_url=None, output_region=None):
    """Write the image into a output region.

    Args::
        url: image
        output_region: output region

    .. note:: The creation of the output 'stage', if this is not done the image is rendered in the page and
        the output region.

    """

    try:
        response = requests.get(image_url)
        stage = widgets.Output(layout={'border': '1px solid green'})
    except:
        print("Error on request : ", image_url)
    else:
        if response.status_code == 200:
            with output_region:
                stage.append_display_data(widgets.Image(
                    value=response.content,
                    # format='jpg',
                    width=300,
                    height=400,
                ))
            output_region.clear_output(wait=True)

"""
Rendering image support within a thread.


"""

def line_box(ele):
    (x, y, w, h) = ele
    return (x, y, x + w, y, x + w, y + h, x, y + h, x, y)


def inscribe_rect(bin_image, detection_box, box_line_width=10):
    """Inscribe box on image

    This is updating the image passed in.

    Args:
        bin_image : binary image
        detection_box : region to put box around
    Return:
        return image -
    """
    draw = ImageDraw.Draw(bin_image)
    draw.line(line_box(detection_box), fill="yellow", width=box_line_width)
    return bin_image


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


def resize_image(bin_image, basewidth=None, baseheight=None):
    """Resize image proportional to the base, make it fit in cell"""
    if basewidth is not None:
        wpercent = (basewidth / float(bin_image.size[0]))
        hsize = int((float(bin_image.size[1]) * float(wpercent)))
        return bin_image.resize((basewidth, hsize), Image.ANTIALIAS)
    wpercent = (baseheight / float(bin_image.size[1]))
    wsize = int((float(bin_image.size[0]) * float(wpercent)))
    return bin_image.resize((wsize, baseheight), Image.ANTIALIAS)

# example image url: https://m.media-amazon.com/images/S/aplus-media/vc/6a9569ab-cb8e-46d9-8aea-a7022e58c74a.jpg
def face_crop(bin_image, detection_box, percent, probability):
    """Crop out the faces from a URL using detection_box and send to analysis.
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
    draw = ImageDraw.Draw(bin_image)
    box_width = 5 if percent > .01 else 20
    box_fill = "orange" if probability > .90 else "red"
    draw.line(line_box(detection_box), fill=box_fill, width=box_width)
    #draw.rectangle(detection_box, fill=128)
    return {'annotated_image':bin_image}


order_index = ['surprise', 'happiness', 'contempt', 'neutral', 'sadness', 'anger', 'disgust', 'fear']
colors = ['hotpink', 'gold', 'lightcoral', 'beige', 'brown', 'red', 'green', 'purple']


def scale(region):
    """Display the scale used on the scoring.

    Args:
        region to write the scale into

    ..note: this invoked when the emotion classifier does not return any results. Put
    up the scale to understand the score.

    """
    with region:
        fz = 150
        fd = -1.30
        plt.text(0.0, 1.0,
                 "{:^35s}".format("Emotion Anlysis Inconclusive"), size=fz,
                 ha="left", va="top",
                 bbox=dict(boxstyle="square",
                           fc="white",
                           fill=True)
                 )

        plt.rcParams['font.family'] = 'monospace'
        for idx in range(len(colors)):
            plt.text(0.0, (fd * idx) + -2,
                     "{:^35s}".format(order_index[idx]), size=fz,
                     ha="left", va="top",
                     bbox=dict(boxstyle="square",
                               fc=colors[idx],
                               fill=True
                               )
                     )

        plt.axis('off')
        plt.show()
        clear_output(wait=True)


bar_idx = 0
img_dict = dict()


def bar_cell(crops_bar, bar_cells, percentage, probability, emotion, crop_img):
    """In cells below main photo the results of the two
    deep learning models are displayed by this function.
    """
    global bar_idx
    with crops_bar[bar_idx % bar_cells]['image']:
        display(resize_image(crop_img, basewidth=100))
        clear_output(wait=True)
    if len(emotion) > 0:
        print(emotion)
        with crops_bar[bar_idx % bar_cells]['pie']:
            fig1, ax1 = plt.subplots()
            emot = [emotion[0][key] for key in order_index]
            # df = pandas.DataFrame(emotion[0], index=order_index)
            ax1.pie(emot,
                    shadow=True, startangle=90, colors=colors)
            ax1.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
            plt.show()
            clear_output(wait=True)
    else:
        scale(crops_bar[bar_idx % bar_cells]['pie'])
    crops_bar[bar_idx % bar_cells]['probability'].value = "conf : {0:.2f}%".format(probability)
    crops_bar[bar_idx % bar_cells]['image_percent'].value = "img {0:.2f}%".format(percentage)
    bar_idx += 1



def render_emotions(emotion_tuples, full_widget, crops_bar, bar_cells):
    """Using view data display the emotion results.

    ..note: We have cropped face image, the location and the url of the original image.
    Display original image with the outline of the image location, I lay multiple onlines
    on the image by holding them in a map, this also reduces the number of times I
    pull from wikipedia.
    """
    for emotion in emotion_tuples:
        img_url = emotion['img_desc'][0]['img']
        percent = emotion['face']['image_percent']
        probability = emotion['face']['probability']

        if (img_url in img_dict):
            print("cache", img_url)
            bimg = decode_img(img_dict[img_url])
            face_crops = face_crop(bimg, emotion['face']['detection_box'], percent, probability)
            img_dict[img_url] = encode_img(face_crops['annotated_image'])
            with full_widget:
                fullImg = face_crops['annotated_image']
                dspImg = resize_image(fullImg, baseheight=400)
                display(dspImg)
                clear_output(wait=True)
        else:
            print("web", img_url)
            r = requests.get(img_url, timeout=4.0)
            if r.status_code != requests.codes.ok:
                assert False, 'Status code error: {}.'.format(r.status_code)
            with Image.open(io.BytesIO(r.content)) as bin_image:
                bimg = bin_image
                # display(bimg)
                face_crops = face_crop(bimg, emotion['face']['detection_box'], percent, probability)
                img_dict[img_url] = encode_img(face_crops['annotated_image'])
                with full_widget:
                    fullImg = face_crops['annotated_image']
                    dspImg = resize_image(fullImg, baseheight=400)
                    display(dspImg)
                    clear_output(wait=True)
        binImg = emotion['face']['bytes_PIL_b64']
        bar_cell(crops_bar, bar_cells, percent,
                 probability,
                 emotion['emotion'],
                 Image.open(io.BytesIO(base64.b64decode(binImg))))





class faceDashboard(object):
    def __init__(self, instance, sleep=2):
        self.instance = instance
        self.status = widgets.Label(value="Source", layout={'border': '1px solid green', 'width': '50%'})
        self.rect = widgets.Output(layout={'border': '1px solid red', 'width': '50%', 'height': '300pt'})
        self.url = widgets.Label(value="URL", layout={'border': '1px solid green', 'width': '50%'})
        self.button = widgets.Button(description='', button_style='danger', layout={'width': '25%'}, disabled=True)

        self.dashboard = widgets.VBox([self.status, self.rect, self.url, self.button])
        # display(self.dashboard)
        self.time_sleep = sleep
        self.execute = threading.Event()
        self.thread = None

    def render_tuples(self, tuples):
        count = 0
        num_tuples = len(tuples)
        self.status.value = "view dequed:{} @ {}".format(num_tuples, time.strftime("%H:%M:%S", time.localtime()))
        for face in tuples:
            self.url.value = face['url']
            # source_face.value = trimmed['source']  # TODO - move accros the source.
            self.status.value = "{} of {}".format(count, num_tuples)
            count += 1
            image_string = face['image_string']
            with Image.open(io.BytesIO(base64.b64decode(image_string))) as bin_image:
                for rect in face['face_regions']:
                    inscribe_rect(bin_image, rect)
                with self.rect:
                    display(resize_image(bin_image, baseheight=600))
                    clear_output(wait=True)
            time.sleep(self.time_sleep)

    def ignition(self, start):
        if start:
            self.thread = threading.Thread(target=self.fetchRender_thread, name="Render_Face")
            self.thread.start()
        else:
            self.execute.clear()
            self.button.description = "Stopping..."
            self.button.disabled = True

    def fetchRender_thread(self):
        self.button.disabled = True
        self.button.description = 'Stop'
        self.button.button_style = 'danger'
        button_action = lambda w: self.ignition(False)
        self.button.on_click(button_action)
        self.button.disabled = False
        self.execute.set()

        # start up
        faces_view = self.instance.get_views(name="faces_view")[0]
        faces_view.start_data_fetch()
        # fetch til button pushed
        while self.execute.is_set():
            faces_tuples = faces_view.fetch_tuples(max_tuples=10, timeout=2)
            self.render_tuples(faces_tuples)
        # shut down
        faces_view.stop_data_fetch()
        #
        self.button.description = 'Stopped'
        self.button.button_style = 'warning'


# Convert to rendering in thread..

class objectDashboard(object):
    def __init__(self, instance, sleep=2):
        self.instance = instance
        self.source = widgets.Label(value="Source", layout={'border': '1px solid green', 'width': '50%'})
        self.rect = widgets.Output(layout={'border': '1px solid red', 'width': '50%', 'height': '300pt'})
        self.url = widgets.Label(value="URL", layout={'border': '1px solid green', 'width': '50%'})
        self._class = widgets.Label(value="CLASS", layout={'border': '1px solid green', 'width': '50%'})
        self.button = widgets.Button(description='', button_style='danger', layout={'width': '25%'}, disabled=True)
        self.dashboard = widgets.VBox([self.source, self.rect, self.url, self.button, self._class])
        self.time_sleep = sleep
        self.execute = threading.Event()
        self.thread = None

    def render_tuples(self, tuples):
        count = 0
        self.source.value = "view dequed:{} @ {}".format(len(tuples), time.strftime("%H:%M:%S", time.localtime()))
        for tuple_object in tuples:
            self.url.value = tuple_object['url']
            self.source.value = "{} of {}".format(count, len(tuples))
            count += 1
            image_string = tuple_object['image_string']
            class_string = ""
            with Image.open(io.BytesIO(base64.b64decode(image_string))) as bin_image:
                for rect in tuple_object['object_regions']:
                    inscribe_rect(bin_image, rect['region'])
                    class_string = ",".join([class_string, rect['class']])
                    self._class.value = class_string
                with self.rect:
                    display(resize_image(bin_image, baseheight=600))
                    clear_output(wait=True)
            if not self.execute.is_set():
                break
            time.sleep(self.time_sleep)

    def ignition(self, start):
        if start:
            self.thread = threading.Thread(target=self.fetchRender_thread, name="Render_View")
            self.thread.start()
        else:
            self.execute.clear()
            self.button.description = "Stopping..."
            self.button.disabled = True

    def fetchRender_thread(self):
        self.button.disabled = True
        self.button.description = 'Stop'
        self.button.button_style = 'danger'
        button_action = lambda w: self.ignition(False)
        self.button.on_click(button_action)
        self.button.disabled = False
        self.execute.set()

        # start up
        objects_view = self.instance.get_views(name="objects_view")[0]
        objects_view.start_data_fetch()
        # fetch til button pushed
        while self.execute.is_set():
            objects_tuples = objects_view.fetch_tuples(max_tuples=100, timeout=2)
            self.render_tuples(objects_tuples)
        # shut down
        objects_view.stop_data_fetch()
        #
        self.button.description = 'Stopped'
        self.button.button_style = 'warning'
