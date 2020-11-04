"""
Example script for event bus usage
"""
import functools
import logging
import os
import time

from oet.observingtasks import publish_event_message

LOG = logging.getLogger(__name__)
FORMAT = '%(asctime)-15s %(message)s'

logging.basicConfig(level=logging.INFO, format=FORMAT)


def init(subarray_id: int):
    global main
    main = functools.partial(_main, subarray_id)
    LOG.info(f'Script bound to sub-array {subarray_id}')


def announce(msg):
    publish_event_message(msg=msg)


def _main(subarray_id: int):
    announce(f'Running event bus script in OS process {os.getpid()}')

    for i in range(10):
        announce(f'executing scan {i}/10')
        time.sleep(1)

    announce('Script complete')
