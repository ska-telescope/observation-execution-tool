import functools
import logging
import os
import threading

from pubsub import pub
from ska_oso_pdm.entities.common.sb_definition import SBDefinition
from ska_oso_pdm.schemas import CODEC as pdm_CODEC

from ska_oso_oet.event import topics

LOG = logging.getLogger(__name__)
FORMAT = "%(asctime)-15s %(message)s"

logging.basicConfig(level=logging.INFO, format=FORMAT)


def announce(msg: str):
    """
    Helper function to send messages via pypubsub.

    :param msg: message to announce
    """
    pub.sendMessage(
        topics.user.script.announce, msg_src=threading.current_thread().name, msg=msg
    )


def init(subarray_id: int):
    global main
    main = functools.partial(_main, subarray_id)
    LOG.info(f"Script bound to sub-array {subarray_id}")


def _main(subarray_id: int, sb_json: os.PathLike, raise_msg=None):
    LOG.info(f"Running script in OS process {os.getpid()}")
    announce(f"Running script in OS process {os.getpid()}")

    if not os.path.isfile(sb_json):
        msg = f"SB file not found: {sb_json}"
        LOG.error(msg)
        raise IOError(msg)

    sbd = pdm_CODEC.load_from_file(SBDefinition, sb_json)

    LOG.info(f"Retrieved SBD {sbd.sbd_id} from filesystem path {sb_json}")
    announce(f"Retrieved SBD {sbd.sbd_id} from filesystem path {sb_json}")

    if raise_msg:
        LOG.error(f"Raising an exception with msg {raise_msg}")
        raise Exception(raise_msg)

    LOG.info("Script complete")
    announce("Script complete")
