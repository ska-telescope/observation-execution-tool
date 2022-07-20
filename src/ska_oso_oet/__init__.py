"""
Reading ska_oso_oet.ini file value and initializing constant of feature toggle
with enabling event based polling/pubsub
"""
import os.path

from pkg_resources import resource_filename
from pubsub import pub
from ska_ser_logging import configure_logging
from tblib import pickling_support

import ska_oso_oet.event.topics

from .features import Features

# Set pypubsub to throw an error if topic in sendMessage does not correspond
# to a topic in the topic tree defined in ska_oso_oet.event.topics
pub.setTopicUnspecifiedFatal(True)

# Load the topic tree definition
pub.addTopicDefnProvider(ska_oso_oet.event.topics, pub.TOPIC_TREE_FROM_CLASS)

configure_logging()
pickling_support.install()

FEATURES = Features.create_from_config_files(
    os.path.expanduser("~/ska_oso_oet.ini"),
    resource_filename(__name__, "ska_oso_oet.ini"),
)
