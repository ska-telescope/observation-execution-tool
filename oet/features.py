"""
The features module contains code allowing the user to configure OET runtime behaviour at
deployment time via a features toggle, such as reading via polling or pubsub, on or off. This can
either be from a default .ini file, a .ini file provided by the user, or by setting defaults if no
file is provided.
"""

from configparser import ConfigParser


class Features:
    """
    The Features class represents the features that can be toggled.
    """
    def __init__(self, config_parser: ConfigParser):
        self._use_pubsub = config_parser.getboolean('tango', 'read_via_pubsub', fallback=False)

    @property
    def use_pubsub_to_read_tango_attributes(self):
        return self._use_pubsub

    @property
    def use_polling_to_read_tango_attributes(self):
        return not self._use_pubsub

    @staticmethod
    def create_from_config_files(*paths) -> 'Features':
        config = ConfigParser()
        # config.read() requires an iterable of paths. The paths tuple is
        # enough to satisfy this requirement.
        config.read(paths)

        return Features(config)
