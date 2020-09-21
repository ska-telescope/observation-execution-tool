import os.path

from .features import Features

FEATURES = Features.create_from_config_files((os.path.expanduser('~/oet/oet.ini'),
                                               os.path.expanduser('~/.oet.ini')))

