"""
Example script for telescope standby
"""
import logging
import os

from oet.domain import SubArray

LOG = logging.getLogger(__name__)
FORMAT = '%(asctime)-15s %(message)s'

logging.basicConfig(level=logging.INFO, format=FORMAT)


def main(subarray_id, *args, **kwargs):
    """
    Reset SubArray.
    """
    LOG.info(f'Running SubArray reset script in OS process {os.getpid()}')

    if args:
        LOG.warning('Got unexpected positional args: %s', args)
    if kwargs:
        LOG.warning('Got unexpected named args: %s', kwargs)

    LOG.info(f'Executing reset...')
    subarray = SubArray(subarray_id)
    subarray.reset()

    LOG.info('SubArray reset script complete')
