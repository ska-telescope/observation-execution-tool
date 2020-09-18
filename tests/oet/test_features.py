"""
Unit tests for the features module
"""

from configparser import ConfigParser

from oet.features import Features


def test_pubsub_feature_returns_true_when_enabled_in_file():
    """
    Something here  for liz to do
    """

    parser = ConfigParser()
    parser.read_dict({'tango': {'read_via_pubsub': True}
                      })

    features = Features(parser)
    assert features.use_pubsub_to_read_tango_attributes is True


def test_pubsub_feature_is_inverse_of_polling_feature():
    """
    Liz to do
    """

    parser = ConfigParser()
    parser.read_dict({'tango': {'read_via_pubsub': True}
                      })

    features = Features(parser)

    assert features.use_pubsub_to_read_tango_attributes is not \
           features.use_polling_to_read_tango_attributes


def test_polling_is_set_as_the_default_read_mechanism():
    """
    Liz to do
    """
    parser = ConfigParser()
    parser.read_dict({})

    features = Features(parser)

    assert features.use_polling_to_read_tango_attributes is True


def test_configparser_strings_are_converted_to_booleans():
    """
    Liz to do - explain why we added this test here.
    """

    for options in ['false', 'False', 'no', 0]:
        parser = ConfigParser()
        parser.read_dict({'tango': {'read_via_pubsub': options}
                          })

        features = Features(parser)

        assert features.use_pubsub_to_read_tango_attributes is False


def test_can_read_config_file(tmpdir):
    """
    Testing that a specified config file can be read by oet
    """

    filename = tmpdir.mkdir("sub").join("blah.ini")

    parser = ConfigParser()
    parser.add_section('tango')

    parser['tango']['read_via_pubsub'] = 'True'

    with open(filename, 'w') as configfile:
        parser.write(configfile)

    features = Features.create_from_config_files(filename)

    assert features.use_polling_to_read_tango_attributes is False
