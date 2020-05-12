"""
Example script for an SB-driven observation.
"""
import logging
import os
from datetime import timedelta

from ska.cdm.messages.subarray_node.configure import ConfigureRequest
from ska.cdm.schemas import CODEC as cdm_CODEC
from ska.pdm.entities.sb_definition import SBDefinition
from ska.pdm.schemas import CODEC as pdm_CODEC

from oet.domain import SubArray
from oet import observingtasks
from oet.command import SCAN_ID_GENERATOR

LOG = logging.getLogger(__name__)
FORMAT = '%(asctime)-15s %(message)s'

logging.basicConfig(level=logging.INFO, format=FORMAT)

#
# Changelog
#
# v1 number of scans and scan duration are sourced from SB
#

def main(sb_json, configure_json, subarray_id=1):
    """
    Observe using a Scheduling Block (SB) and template CDM file.

    :param sb_json: file containing SB in JSON format
    :param configure_json: configuration file in JSON format
    :param subarray_id: numeric subarray ID
    :return:
    """
    LOG.info(f'Running observe_sb script in OS process {os.getpid()}')
    LOG.info(f'Called with sb_json={sb_json}, configure_json={configure_json}, '
             f'subarray_id={subarray_id})')

    if not os.path.isfile(sb_json):
        msg = f'SB file not found: {sb_json}'
        LOG.error(msg)
        raise IOError(msg)

    if not os.path.isfile(configure_json):
        msg = f'CDM file not found: {configure_json}'
        LOG.error(msg)
        raise IOError(msg)

    # Potentially call these within a try ... except block
    sched_block: SBDefinition = pdm_CODEC.load_from_file(SBDefinition, sb_json)
    cdm_config: ConfigureRequest = cdm_CODEC.load_from_file(ConfigureRequest, configure_json)

    subarray = SubArray(subarray_id)

    LOG.info(f'Starting observing for scheduling block: {sched_block.id}')

    # Scan sequence is an ordered list of ScanDefinition identifiers. These
    # are string IDs, not the ScanDefinition instances themselves.
    for scan_definition_id in sched_block.scan_sequence:
        # Get the scan ID. This is only used for logging, not for any
        # business logic.
        scan_id = SCAN_ID_GENERATOR.value

        # We need the ScanDefinition with matching ID. We could inspect each
        # ScanDefinition and return the one with matching ID, or we could do
        # as we do here, creating a temporary mapping and retrieving by key.
        scan_definitions = {scan_definition.id: scan_definition
                            for scan_definition in sched_block.scan_definitions}
        scan_definition = scan_definitions[scan_definition_id]

        LOG.info(f'Configuring for scan definition: {scan_definition.id}')

        # Override the scan duration specified in the CDM with the scan
        # duration extracted from the SB. Note that the CDM library requires
        # scan durations to be timedelta instances, not floats.
        sb_scan_duration = scan_definition.scan_duration
        cdm_config.tmc.scan_duration = timedelta(seconds=sb_scan_duration)
        LOG.info(f'Setting scan duration: {sb_scan_duration} seconds')

        # With the CDM modified, we can now issue the Configure instruction...
        LOG.info(f'Configuring subarray {subarray_id} for scan {scan_id}')
        observingtasks.configure_from_cdm(subarray_id, cdm_config)

        # .. and with configuration complete, we can begin the scan.
        LOG.info(f'Starting scan {scan_id}')
        subarray.scan()

    # All scans are complete. Observations are concluded with an 'end SB'
    # command.
    LOG.info(f'End scheduling block: {sched_block.id}')
    subarray.end_sb()

    LOG.info('Observation script complete')
