"""
This script will be loaded into the OET filesystem and can be used to verify the
behaviour of the Activity domain.

As an Activity requires an SBDefinition in the ODA, first use the ODA API via the Swagger UI at
    http://<KUBE_HOST>/<KUBE_NAMESPACE>/oda/api/v<ODA_MAJOR_VERSION>/ui/
to upload one of the SBDefinitions in the json files in this directory.

Inspect the response to find the SBDefinition sbd_id just created.

Then from the OET CLI, execute
    ``oet activity run observe <sbd_id>``

The event messages should appear in the CLI stream, and the eb_id should be queryable in the ODA.
"""
import functools
import logging
import os
import threading
import time

from pubsub import pub

from ska_oso_pdm import SBDefinition

from ska_oso_scripting.event import user_topics
from ska_oso_scripting import oda_helper

LOG = logging.getLogger(__name__)
FORMAT = "%(asctime)-15s %(message)s"

logging.basicConfig(level=logging.INFO, format=FORMAT)


def announce(msg: str):
    """
    Helper function to send messages via pypubsub.

    :param msg: message to announce
    """
    pub.sendMessage(
        user_topics.script.announce, msg_src=threading.current_thread().name, msg=msg
    )


def init(subarray_id: int, init_arg=None):
    global main
    main = functools.partial(_main, subarray_id)
    LOG.info(f"Script bound to sub-array {subarray_id} with init_arg {init_arg}")


def _main(
    subarray_id: int, sb_json: str, sbi_id: str = "sbi-default-123", raise_msg=None,  *args, **kwargs
):
    LOG.info(f"Running script in OS process {os.getpid()}")

    LOG.info(f"Loading SB from file {sb_json}")
    with open(sb_json, "r", encoding="utf-8") as fh:
        sb = SBDefinition.model_validate_json(fh.read())
    LOG.info(f"Loaded SB with ID {sb.sbd_id}")
    announce(f"Loaded SB with ID {sb.sbd_id}")

    LOG.info(f"Creating EB for SBI {sbi_id}")
    announce(f"Pretending to create EB for SBI {sbi_id}")
    eb_id = oda_helper.create_eb(sb.telescope, sbi_ref=sbi_id)

    LOG.info(f"Created EB {eb_id}")
    announce(f"Created EB {eb_id}")

    for scan_def in sb.scan_definitions:
        LOG.info(f"pretending to execute scan {scan_def.scan_definition_id}")
        announce(f"pretending to execute scan {scan_def.scan_definition_id}")
        time.sleep(1)

    if raise_msg:
        LOG.error(f"Raising an exception with msg {raise_msg}")
        raise Exception(raise_msg)

    LOG.info("Script complete")
    announce("Script complete")
