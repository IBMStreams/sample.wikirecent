import pandas as pd

from IPython.core.debugger import set_trace
from IPython.display import display, clear_output

from statistics import mean
from collections import deque
from collections import Counter

import matplotlib.pyplot as plt
import ipywidgets as widgets
#%matplotlib inline

from sseclient import SSEClient as EventSource

from ipywidgets import Button, HBox, VBox, Layout

from streamsx.topology.topology import *
import streamsx.rest as rest

import streamsx.topology.context
print("streamsx package version: " + streamsx.topology.context.__version__)