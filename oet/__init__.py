import os.path

from .features import Features

FEATURES = Features.create_from_config_files('oet.ini', os.path.expanduser('~/.oet.ini'))
