"""
Jupyter Streams helper functions..

Collection  of functions to submit and monitor Streams on appliations

Accessing Streams Instance & views - currently this is how you define instance and the cfg.

Notes:
    * To submit toplogy to cloud....
    .. code_block:: python
    instance,cfg = jupyter_streams.get_instance(service_name='Streaming3Turbine')
    topo = Function generate topology.....
    jupyter_streams.commonSubmit(cfg, "Streaming3Turbine", topo, credential=credential)

    * anonter notes




"""
import os
import ipywidgets as widgets
import matplotlib.pyplot as plt
from IPython.display import display, clear_output
from ipywidgets import HBox, Layout
import streamsx
from streamsx.topology.topology import *
import streamsx.rest as rest
from streamsx.topology import context

from streamsx.topology.schema import CommonSchema
from streamsx.eventstreams.schema import Schema

## TODO replace for streams_aid
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

def get_instance(cfg, service_name="Steaming3Turbine"):
    """Setup to access your Streams instance.

    Args:
        service_name : on cloud name of the service that you have instantiated.
                       ICP4DF - document
        cfg : Null for Cloud
              Something for CLP4D
    Note:
        The notebook is work within Cloud and ICP4D.
            Refer to the 'Setup' cells above.
    Returns:
        instance : Access to Streams instance, used for submitting and rendering views.
    """
    try:
        from icpd_core import icpd_util
        import urllib3
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




def commonSubmit(_cfg, streams_cloud_service, _topo, credential=None, DEBUG_BUILD=False):
    """submit to either the cloud or CP4D
    Args:
        _cfg: when submitting from CP4D.
        streams_cloud_service (str) : when submitting to cloud, the name of the service credential.py
        must appropriate mapping
        _topo (topology): topology to submit
        DEBUG_BUILD : build and do push archive, print out location of archive.
    Returns:
        What does it return
    Raises:
        NameYourError: The ``Raises`` is a list of all the exceptions
    Hints :
        -  Credentials are from module credentia
        -  fetching the


    """
    if _cfg is not None:
        # Disable SSL certificate verification if necessary
        _cfg[context.ConfigParams.SSL_VERIFY] = False
        submission_result = context.submit("DISTRIBUTED",_topo, config=_cfg)
    if _cfg is None:

        cloud = {
            context.ConfigParams.VCAP_SERVICES: credential.vcap_conf,
            context.ConfigParams.SERVICE_NAME: streams_cloud_service,
            context.ContextTypes.STREAMING_ANALYTICS_SERVICE:"STREAMING_ANALYTIC",
            context.ConfigParams.FORCE_REMOTE_BUILD: True,
        }
        if not DEBUG_BUILD:
            submission_result = context.submit("STREAMING_ANALYTICS_SERVICE",_topo,config=cloud)
        else:
            submission_result = context.submit("BUILD_ARCHIVE",_topo,config=cloud)
            print("archive can be found:", submission_result)

    # The submission_result object contains information about the running application, or job
    if submission_result.job:
        report = "JobId:{} Name:{} ".format(submission_result['id'], submission_result['name'])
    else:
        report = "Somthing did work:{}".format(submission_result)

try:
    print("JAVA_HOME is set to",os.environ["JAVA_HOME"])
except KeyError as err:
    os.environ["JAVA_HOME"] = "/Library/Java/JavaVirtualMachines/jdk1.8.0_221.jdk/Contents/Home"
    print("Had to set JAVA_HOME is set to",os.environ["JAVA_HOME"],"\n   --- what is going on here...")



## TODO streams_aid
def find_job(instance, job_name=None):
    """locate job within instance"""
    for job in instance.get_jobs():
        if job.applicationName.split("::")[-1] == job_name:
            return job
    else:
        return None

## TODO streams_aid
def display_views(instance, job_name):
    """Locate/promote and display all views of a job"""
    job = find_job(instance, job_name=job_name)
    if job is None:
        print("Failed to locate job")
    else:
        views = job.get_views()
        view_events(views)

## TODO streams_aid
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
# TODO moved to streams_aid()
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
