"""
Example script for abort sub-array activity
"""
import os
import logging

from oet.domain import SubArray


LOG = logging.getLogger(__name__)
FORMAT = '%(asctime)-15s %(message)s'

logging.basicConfig(level=logging.INFO, format=FORMAT)


def main(subarray_id=1, *args, **kwargs):
    """
    Send the 'abort' command to the SubArrayNode, halt the subarray
    activity.

    :param subarray: the subarray to command
    :return:
    """
    LOG.info(f'Running abort script in OS process {os.getpid()}')

    if args:
        LOG.warning('Got unexpected positional args: %s', args)
    if kwargs:
        LOG.warning('Got unexpected named args: %s', kwargs)

    LOG.info(f'Called with main(subarray_id={subarray_id})')

    subarray = SubArray(subarray_id)

    LOG.info(f'aborting subarray {subarray_id} activity')

    subarray.abort()

    LOG.info('Observation script complete')

