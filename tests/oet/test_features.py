"""
Unit tests for the features module
"""

from configparser import ConfigParser
from oet.features import Features
import oet


def test_pubsub_feature_returns_true_when_enabled_in_file():
    """
    Test to ensure that the 'use pubsub' toggle returns 'true' when enabled.
    """

    parser = ConfigParser()
    parser.read_dict({'tango': {'read_via_pubsub': True}
                      })

    features = Features(parser)
    assert features.use_pubsub_to_read_tango_attributes is True


def test_pubsub_feature_is_inverse_of_polling_feature():
    """
    Test to ensure that when pubsub is enabled, polling is disabled
    """

    parser = ConfigParser()
    parser.read_dict({'tango': {'read_via_pubsub': True}
                      })

    features = Features(parser)

    assert features.use_pubsub_to_read_tango_attributes is not \
           features.use_polling_to_read_tango_attributes


def test_polling_is_set_as_the_default_read_mechanism():
    """
    Test to make sure that, in the absence of a config file, polling is set as the default
    mechanism for reading from tango.
    """
    parser = ConfigParser()
    parser.read_dict({})

    features = Features(parser)

    assert features.use_polling_to_read_tango_attributes is True


def test_configparser_strings_are_converted_to_booleans():
    """
    ConfigParser reads everything in as a string, which can lead to some odd behaviour when
    converting 'False' to a boolean. Testing that all possible values for False are correctly
    interpreted.
    """

    for options in ['false', 'False', 'no', 0]:
        parser = ConfigParser()
        parser.read_dict({'tango': {'read_via_pubsub': options}
                          })

        features = Features(parser)

        assert features.use_pubsub_to_read_tango_attributes is False


def test_can_read_config_file(tmpdir):
    """
    Testing that a specified config file can be read by OET
    """

    filename = tmpdir.mkdir("sub").join("blah.ini")

    parser = ConfigParser()
    parser.add_section('tango')

    parser['tango']['read_via_pubsub'] = 'True'

    with open(filename, 'w') as configfile:
        parser.write(configfile)

    features = Features.create_from_config_files(filename)

    assert features.use_polling_to_read_tango_attributes is False


def test_default_config_file_is_read_if_present():
    """
    Test to make sure that the default config file is read if it is present
    Added to catch a bug found during code review
    """

    assert oet.FEATURES.use_polling_to_read_tango_attributes is True

