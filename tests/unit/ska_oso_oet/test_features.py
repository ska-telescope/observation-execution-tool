# BTN-1394
"""
Unit tests for the features module
"""
from importlib import resources


def test_default_config_file_is_packaged():
    """
    Test to make sure that the default config file is packaged.
    Added to catch a bug found during code review.
    """
    assert resources.is_resource("ska_oso_oet", "ska_oso_oet.ini")
