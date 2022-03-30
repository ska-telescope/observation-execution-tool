"""
Acceptance test script: Script raises an exception
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
    Script should raise an exception when main function is run.
    """
    raise Exception("Script failed!")
