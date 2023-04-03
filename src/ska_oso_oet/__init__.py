"""
Reading ska_oso_oet.ini file value and initializing constant of feature toggle
with enabling event based polling/pubsub
"""
import os.path

from pkg_resources import resource_filename
from pubsub import pub
from tblib import pickling_support

import ska_oso_oet.event.topics

# backwards compatibility with ska-oso-oet < 5.0.0, to be removed once
# ska-oso-scripting has been updated to use tango module
from . import tango as command  # noqa: F401
from .features import Features

# Set pypubsub to throw an error if topic in sendMessage does not correspond
# to a topic in the topic tree defined in ska_oso_oet.event.topics
pub.setTopicUnspecifiedFatal(True)

# Load the topic tree definition
pub.addTopicDefnProvider(ska_oso_oet.event.topics, pub.TOPIC_TREE_FROM_CLASS)

pickling_support.install()

FEATURES = Features.create_from_config_files(
    os.path.expanduser("~/ska_oso_oet.ini"),
    resource_filename(__name__, "ska_oso_oet.ini"),
)
