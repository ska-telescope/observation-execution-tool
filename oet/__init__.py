"""
Reading oet.ini file value and initializing constant of feature toggle with enabling
event based polling/pubsub
"""
import os.path

from ska.logging import configure_logging
from tblib import pickling_support

from .features import Features

import oet.event.topics
from pubsub import pub

# Set pypubsub to throw an error if topic in sendMessage does not correspond
# to a topic in the topic tree defined in oet.event.topics
pub.setTopicUnspecifiedFatal(True)

# Load the topic tree definition
pub.addTopicDefnProvider(oet.event.topics, pub.TOPIC_TREE_FROM_CLASS)

configure_logging()
pickling_support.install()

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

FEATURES = Features.create_from_config_files(os.path.expanduser('~/oet.ini'),
                                             os.path.join(os.path.split(ROOT_DIR)[0], 'oet.ini'))
