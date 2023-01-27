import functools
import logging
import os
import threading
import time

from pubsub import pub

from ska_oso_pdm.entities.common.sb_definition import SBDefinition
from ska_oso_pdm.schemas import CODEC

from ska_oso_oet.event import topics

LOG = logging.getLogger(__name__)
FORMAT = '%(asctime)-15s %(message)s'

logging.basicConfig(level=logging.INFO, format=FORMAT)


def announce(msg: str):
    """
    Helper function to send messages via pypubsub.

    :param msg: message to announce
    """
    pub.sendMessage(topics.user.script.announce, msg_src=threading.current_thread().name, msg=msg)


def init(subarray_id: int):
    global main
    main = functools.partial(_main, subarray_id)
    LOG.info(f'Script bound to sub-array {subarray_id}')


def _main(subarray_id: int, sb_json: str, raise_msg=None):
    LOG.info(f'Running script in OS process {os.getpid()}')

    LOG.info(f'Loading SB from file {sb_json}')
    sb: SBDefinition = CODEC.loads(SBDefinition, sb_json)
    LOG.info(f'Loaded SB with ID {sb.sbd_id}')
    announce(f'Loaded SB with ID {sb.sbd_id}')

    for scan_def in sb.scan_definitions:
        LOG.info(f'pretending to execute scan {scan_def.scan_definition_id}')
        announce(f'pretending to execute scan {scan_def.scan_definition_id}')
        time.sleep(1)

    if raise_msg:
        LOG.error(f'Raising an exception with msg {raise_msg}')
        raise Exception(raise_msg)

    LOG.info('Script complete')
    announce('Script complete')
