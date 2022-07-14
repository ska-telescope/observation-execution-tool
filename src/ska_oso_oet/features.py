# BTN-1394
"""
The features module contains code handling the setting and reading of OET
feature flags. OET feature flags are configured once, at deployment time, and
are not reconfigured during execution.

Feature flag values are set from, in order:

  1. environment variables,
  2. an .ini file
  3. default values set in code
"""
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
        pass

    @staticmethod
    def create_from_config_files(*paths) -> "Features":
        """
        Create a new Features instance from a set of feature flag
        configuration files.

        :param paths: configuration files to parse
        """
        config = ConfigParser()
        # config.read() requires an iterable of paths. The paths tuple is
        # enough to satisfy this requirement.
        config.read(paths)
        return Features(config)
