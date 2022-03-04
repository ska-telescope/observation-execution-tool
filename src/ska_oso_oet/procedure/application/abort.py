"""
Example script for abort sub-array activity
"""
import functools
import logging
import os

from ska_oso_oet.command import Attribute, Command, TangoExecutor

LOG = logging.getLogger(__name__)
FORMAT = "%(asctime)-15s %(message)s"

logging.basicConfig(level=logging.INFO, format=FORMAT)
EXECUTOR = TangoExecutor()


def main(*args, **kwargs):
    LOG.warning(
        "Deprecated! Calling main before sub-array is bound will be removed for PI9"
    )
    _main(*args, **kwargs)


def init(subarray_id: int):
    global main
    main = functools.partial(_main, subarray_id)
    LOG.info(f"Script bound to sub-array {subarray_id}")


def _main(subarray_id: int, *args, **kwargs):
    """
    Send the 'abort' command to the SubArrayNode, halt the subarray
    activity.

    :param subarray_id: numeric subarray ID
    :return:
    """
    LOG.info(f"Running abort script in OS process {os.getpid()}")

    if args:
        LOG.warning("Got unexpected positional args: %s", args)
    if kwargs:
        LOG.warning("Got unexpected named args: %s", kwargs)

    LOG.info(f"Called with main(subarray_id={subarray_id})")

    subarray_fqdn = (
        os.getenv("SUBARRAYNODE_FQDN_PREFIX", "ska_mid/tm_subarray_node")
        + "/"
        + str(subarray_id)
    )
    cmd = Command(subarray_fqdn, "Abort")
    attr = Attribute(subarray_fqdn, "obsState")

    LOG.info(f"Aborting subarray {subarray_id}")
    event_id = EXECUTOR.subscribe_event(attr)

    EXECUTOR.execute(cmd)
    _wait_for_abort_state(attr)
    EXECUTOR.unsubscribe_event(attr, event_id)

    LOG.info("Abort script complete")


def _wait_for_abort_state(attr: Attribute):
    while True:
        event = EXECUTOR.read_event(attr)
        if event.attr_value.value == 7:
            LOG.info("Subarray reached state ABORTED")
            return True
