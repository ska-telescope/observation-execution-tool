"""
Reading oet.ini file value and initializing constant of feature toggle with enabling
event based polling/pubsub
"""
import os.path
import logging

from ska.logging import configure_logging

from .features import Features

import oet.event.topics
from pubsub import pub

pub.setTopicUnspecifiedFatal(True)
pub.addTopicDefnProvider(oet.event.topics, pub.TOPIC_TREE_FROM_CLASS)

configure_logging()

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

FEATURES = Features.create_from_config_files(os.path.expanduser('~/oet.ini'),
                                             os.path.join(os.path.split(ROOT_DIR)[0], 'oet.ini'))
