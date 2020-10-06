"""
Reading oet.ini file value and initializing constant of feature toggle with enabling
event based polling/pubsub
"""
import os.path

from .features import Features

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

FEATURES = Features.create_from_config_files(os.path.expanduser('~/oet.ini'),
                                             os.path.join(os.path.split(ROOT_DIR)[0], 'oet.ini'))
