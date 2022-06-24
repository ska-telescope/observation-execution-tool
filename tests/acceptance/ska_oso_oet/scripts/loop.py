# BTN-1394
"""
Acceptance test script: Script hangs/runs forever
"""
import functools
import os


def init(subarray_id):
    """
    Initialise the script
    """
    global main
    main = functools.partial(_main, subarray_id)


def _main(subarray_id):
    """
    Script should not complete unless process is killed.
    """
    while True:
        os.path.exists("/tmp/scripts/hello.py")
