"""
Example script for telescope startup
"""
import logging
import os

from oet.domain import SKAMid
from oet import observingtasks
from oet.event import topics

LOG = logging.getLogger(__name__)
FORMAT = '%(asctime)-15s %(message)s'

logging.basicConfig(level=logging.INFO, format=FORMAT)


def init(*args, subarray_id):
    pass


def main(*args, **kwargs):
    """
    Start up telescope.
    """
    # raise Exception("Exception occured in the test script!!")
    observingtasks.publish_event_message(msg="2222")
    print("hello world")
