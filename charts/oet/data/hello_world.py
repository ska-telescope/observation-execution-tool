import functools
import logging
import os
import time


LOG = logging.getLogger(__name__)
FORMAT = '%(asctime)-15s %(message)s'

logging.basicConfig(level=logging.INFO, format=FORMAT)


def init(subarray_id: int):
    global main
    main = functools.partial(_main, subarray_id)
    LOG.info(f'Script bound to sub-array {subarray_id}')


def _main(subarray_id: int, raise_msg=None):
    LOG.info(f'Running script in OS process {os.getpid()}')

    for i in range(5):
        LOG.info(f'pretending to execute scan {i}/10')
        time.sleep(1)

    if raise_msg:
        LOG.error(f'Raising an exception with msg {raise_msg}')
        raise Exception(raise_msg)

    LOG.info('Script complete')
