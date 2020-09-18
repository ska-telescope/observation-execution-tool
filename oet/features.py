"""
Liz to write something meaningful here
"""

from configparser import ConfigParser



class Features:
    """
    explain the class here
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
