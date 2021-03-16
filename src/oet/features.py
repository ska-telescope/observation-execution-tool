"""
The features module contains code handling the setting and reading of OET
feature flags. OET feature flags are configured once, at deployment time, and
are not reconfigured during execution.

Feature flag values are set from, in order:

  1. environment variables,
  2. an .ini file
  3. default values set in code
"""
import distutils.util
import os
from configparser import ConfigParser


class Features:
    """
    The Features class holds flags for OET features that can be toggled.
    """

    def __init__(self, config_parser: ConfigParser):
        # Get the feature flag value first from the environment, second from
        # the ini file, else from code default. The requirement to convert
        # environment variable strings to booleans makes this uglier than
        # ideal.
        if "OET_READ_VIA_PUBSUB" in os.environ:
            env_value = os.environ.get("OET_READ_VIA_PUBSUB")
            self._use_pubsub = bool(distutils.util.strtobool(env_value))
        else:
            self._use_pubsub = config_parser.getboolean(
                "tango", "read_via_pubsub", fallback=False
            )

    @property
    def use_pubsub_to_read_tango_attributes(self) -> bool:
        return self._use_pubsub

    @property
    def use_polling_to_read_tango_attributes(self) -> bool:
        return not self._use_pubsub

    @staticmethod
    def create_from_config_files(*paths) -> "Features":
        config = ConfigParser()
        # config.read() requires an iterable of paths. The paths tuple is
        # enough to satisfy this requirement.
        config.read(paths)
        return Features(config)
