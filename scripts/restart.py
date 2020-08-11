"""
Example script for restarting sub-array. Restarting will deallocate all dishes.
"""
import logging
import os

from oet.domain import SubArray

LOG = logging.getLogger(__name__)
FORMAT = '%(asctime)-15s %(message)s'

logging.basicConfig(level=logging.INFO, format=FORMAT)


def main(subarray_id, *args, **kwargs):
    """
    Restart SubArray. SubArray state should be EMPTY if restart is successful.
    """
    LOG.info(f'Running SubArray restart script in OS process {os.getpid()}')

    if args:
        LOG.warning('Got unexpected positional args: %s', args)
    if kwargs:
        LOG.warning('Got unexpected named args: %s', kwargs)

    LOG.info(f'Executing restart...')
    subarray = SubArray(subarray_id)
    subarray.restart()

    LOG.info('SubArray restart script complete')
