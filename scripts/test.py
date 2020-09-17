"""
Example script for telescope startup
"""
import logging
import os

from oet.domain import SKAMid

LOG = logging.getLogger(__name__)
FORMAT = '%(asctime)-15s %(message)s'

logging.basicConfig(level=logging.INFO, format=FORMAT)


def init(subarray_id):
    pass


def main(*args, **kwargs):
    """
    Start up telescope.
    """
    raise Exception("Exception occured in the test script!!")
    # print("hello world")
