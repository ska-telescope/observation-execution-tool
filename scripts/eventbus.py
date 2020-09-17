"""
Example script for event bus usage
"""
import functools
import logging
import os
import time

from pubsub import pub

LOG = logging.getLogger(__name__)
FORMAT = '%(asctime)-15s %(message)s'

logging.basicConfig(level=logging.INFO, format=FORMAT)


def init(subarray_id: int):
    global main
    main = functools.partial(_main, subarray_id)
    LOG.info(f'Script bound to sub-array {subarray_id}')


def announce(msg):
    pub.sendMessage(topicName='user.script.announce', msg=msg)


def _main(subarray_id: int):
    announce(f'Running event bus script in OS process {os.getpid()}')

    for i in range(10):
        announce(f'executing scan {i}/10')
        time.sleep(1)

    announce('Script complete')
