import logging
import os
import threading

from emoji import emojize
from pubsub import pub

from ska_oso_oet.event import topics

LOG = logging.getLogger(__name__)
FORMAT = "%(asctime)-15s %(message)s"

logging.basicConfig(level=logging.INFO, format=FORMAT)


def announce(msg: str):
    """
    Helper function to send OET messages

    :param msg: message to announce
    """
    pub.sendMessage(
        topics.user.script.announce,
        msg_src=threading.current_thread().name,
        # uses emoji library function. Not installed in default environment
        msg=emojize(msg),
    )


def main(msg=None):
    announce(f":desktop_computer: running git script in OS process {os.getpid()}")
    if msg:
        announce(msg)

    num_scans = 5
    for i in range(1, num_scans + 1):
        announce(f":milky_way: executing scan {i}/{num_scans}")
        announce(f":milky_way: scan {i} complete")
        if msg:
            announce(msg)

    announce(f":desktop_computer: script complete")
