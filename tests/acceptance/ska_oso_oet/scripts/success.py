"""
Acceptance test script: Script runs successfully
"""
import functools


def init(subarray_id):
    """
    Initialise the script
    """
    global main
    main = functools.partial(_main, subarray_id)


def _main(subarray_id):
    """
    Script should execute successfully so no need to do anything here.
    """
    pass
