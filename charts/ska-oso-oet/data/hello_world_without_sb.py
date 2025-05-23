"""
This script will be loaded into the OET filesystem and can be used to verify the
behaviour of the Procedure domain.

From the OET CLI, execute
    ``oet procedure create file:///tmp/scripts/hello_world_without_sb.py``

Then get the PID and that the Procedure is READY with
    ``oet procedure list``

Then start the Procedure with
    ``oet procedure start --pid=<PID>``
"""
import functools
import logging
import os
import threading
import time

from pubsub import pub
from ska_oso_scripting.event import user_topics

LOG = logging.getLogger(__name__)
FORMAT = '%(asctime)-15s %(message)s'

logging.basicConfig(level=logging.INFO, format=FORMAT)


def announce(msg: str):
    """
    Helper function to send messages via pypubsub.

    :param msg: message to announce
    """
    pub.sendMessage(user_topics.script.announce, msg_src=threading.current_thread().name, msg=msg)


def init(subarray_id: int, init_arg=None):
    global main
    main = functools.partial(_main, subarray_id)
    LOG.info(f'Script bound to sub-array {subarray_id} with init_arg {init_arg}')


def _main(subarray_id: int, raise_msg=None, *args, **kwargs):
    LOG.info(f'Running script in OS process {os.getpid()} with args {args} and kwargs {kwargs}')
    announce(f'Running script in OS process {os.getpid()} with args {args} and kwargs {kwargs}')

    for i in range(1, 10):
        LOG.info(f'pretending to execute scan {i}/10')
        announce(f'pretending to execute scan {i}/10')
        time.sleep(1)

    if raise_msg:
        LOG.error(f'Raising an exception with msg {raise_msg}')
        raise Exception(raise_msg)

    LOG.info('Script complete')
    announce('Script complete')
