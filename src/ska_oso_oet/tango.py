"""
The tango module contains code that encapsulates Tango device interactions
(commands, attribute read/writes, etc.) and provides the means to execute
them.

The OET decouples functions from Tango devices so that the commands can be
managed and executed by a proxy. This allows the proxy to execute commands
asynchronously while listening for interrupt signals, while to the caller
the execution appears synchronous.
"""
from __future__ import annotations
import logging
import multiprocessing
import os
from ska_ser_skuid.client import SkuidClient

LOGGER = logging.getLogger(__name__)


class LocalScanIdGenerator:  # pylint: disable=too-few-public-methods
    """
    LocalScanIdGenerator is an abstraction of a service that will generate scan
    IDs as unique integers. Expect scan UID generation to be a database
    operation or similar in the production implementation.
    """

    def __init__(self, start=1):
        self.backing = multiprocessing.Value("i", start)

    @property
    def value(self):
        """
        Get the current scan ID.
        """
        with self.backing.get_lock():
            return self.backing.value

    def next(self):
        """
        Get the next scan ID.

        :return: integer scan ID
        """
        previous_scan_id = self.value
        with self.backing.get_lock():
            self.backing.value += 1
            return previous_scan_id


class RemoteScanIdGenerator:  # pylint: disable=too-few-public-methods
    """
    RemoteScanIdGenerator connects to the skuid service to retrieve IDs
    """

    def __init__(self, hostname):
        self.skuid_client = SkuidClient(hostname)
        self.backing = multiprocessing.Value("i", -1)

    @property
    def value(self):
        """
        Get the current scan ID.
        """
        with self.backing.get_lock():
            # Default value, scan id's should be > 0
            if self.backing.value == -1:
                self.next()
            return self.backing.value

    def next(self):
        """
        Get the next scan ID.

        :return: integer scan ID
        """
        with self.backing.get_lock():
            self.backing.value = self.skuid_client.fetch_scan_id()
            return self.backing.value


# hold scan ID generator at the module level
if "SKUID_URL" in os.environ:
    # SKUID_URL should be in the format HOST:PORT
    SCAN_ID_GENERATOR = RemoteScanIdGenerator(os.environ["SKUID_URL"])
else:
    SCAN_ID_GENERATOR = LocalScanIdGenerator()

