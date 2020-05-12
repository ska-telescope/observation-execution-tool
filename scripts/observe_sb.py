"""
Example script for resource allocation
"""
import os
import logging
from datetime import timedelta


from oet.domain import SubArray
from ska.pdm.entities.sb_definition import SBDefinition
from ska.cdm.messages.subarray_node.configure import ConfigureRequest
from ska.pdm.schema import CODEC as pdm_CODEC
from ska.cdm.schemas import CODEC as cdm_CODEC

LOG = logging.getLogger(__name__)
FORMAT = '%(asctime)-15s %(message)s'

logging.basicConfig(level=logging.INFO, format=FORMAT)


def main(sb_json, configure_json, subarray_id=1):
    """
    Configure a Scheduling Block (SB) and perform the scan.

    :param sb_json: file containing SB in JSON format
    :param configure_json: configuration file in JSON format
    :param subarray_id: numeric subarray ID
    :return:
    """
    LOG.info(f'Running observe_sb script in OS process {os.getpid()}')
    LOG.info(f'Called with sb_json={sb_json}, configure_json={configure_json}, '
             f'subarray_id={subarray_id})')

    if not os.path.isfile(sb_json):
        msg = f'File not found: {sb_json}'
        LOG.error(msg)
        raise IOError(msg)

    if not os.path.isfile(configure_json):
        msg = f'File not found: {configure_json}'
        LOG.error(msg)
        raise IOError(msg)
    
    # Potentially call these within a try ... except block
    sched_block = pdm_CODEC.load_from_file(SBDefinition, sb_json)
    cdm_config = cdm_CODEC.load_from_file(ConfigureRequest, configure_json)

    subarray = SubArray(subarray_id)
    
    
    for scan_def in sched_block.ScanSequence:
        scan_duration = scan_def.scan_duration
        scan_duration_delta = timedelta(seconds=scan_duration)
        cdm_config.tmc.scan_duration = scan_duration_delta
        LOG.info(f'Configuring subarray with scan duration {scan_duration} seconds')
        configure_from_cdm(subarray_id, cdm_config)
        LOG.info(f'Starting scan')
        subarray.scan()


    LOG.info('End scheduling block')
    subarray.end_sb()

    LOG.info('Observation script complete')
