"""
Example script for resource allocation from file
"""
import logging
import os

from oet.domain import Dish, ResourceAllocation, SKAMid, SubArray

LOG = logging.getLogger(__name__)
FORMAT = '%(asctime)-15s %(message)s'

logging.basicConfig(level=logging.INFO, format=FORMAT)


def main(configuration, subarray_id=1, process_json=True):
    """
    Allocate resources to a target sub-array.

    :param configuration: name of configuration file
    :param subarray_id: numeric subarray ID
    :param process_json: set to False to pass JSON directly to TMC without processing
    :return:
    """

    LOG.info(f'Running allocate script in OS process {os.getpid()}')
    LOG.info(f'Called with main(configuration={configuration}, subarray_id={subarray_id}, '
             f'process_json={process_json}')

    subarray = SubArray(subarray_id)

    LOG.info(f'Allocating resources')
    allocated = subarray.allocate_from_file(configuration, process_json)
    LOG.info(f'Resources Allocated: {allocated}')

    LOG.info('Allocation script complete')
