"""
Unit tests for the features module
"""
from configparser import ConfigParser
import os
from pkg_resources import resource_exists

from oet.features import Features
from unittest import mock


def test_pubsub_precedence():
    """
    Test that feature flags are set in the expected order:
      1. by environment variable
      2. by oet.ini file
      3. default value set in code
    """
    # get the default value by supplying a parser with no flags set
    parser = ConfigParser()
    default_value = Features(parser).use_pubsub_to_read_tango_attributes

    # set the flag value in the file to the inverse of the default but leave
    # the environment variable unset. If files take precedence over defaults,
    # we should get this value back.
    file_value = not default_value
    parser.read_dict({"tango": {"read_via_pubsub": file_value}})
    assert Features(parser).use_pubsub_to_read_tango_attributes == file_value

    # Finally, run that last test again but with an environment variable set
    # to the inverse of the file value. The feature flag should now return
    # the value of this environment variable.
    env_value = not file_value
    with mock.patch.dict(os.environ, {"OET_READ_VIA_PUBSUB": str(env_value)}):
        assert Features(parser).use_pubsub_to_read_tango_attributes == env_value


def test_pubsub_feature_returns_true_when_enabled_in_file():
    """
    Test to ensure that the 'use pubsub' toggle returns 'true' when enabled.
    """
    parser = ConfigParser()
    parser.read_dict({"tango": {"read_via_pubsub": True}})

    features = Features(parser)
    assert features.use_pubsub_to_read_tango_attributes is True


def test_pubsub_feature_is_inverse_of_polling_feature():
    """
    Test to ensure that when pubsub is enabled, polling is disabled
    """
    parser = ConfigParser()
    parser.read_dict({"tango": {"read_via_pubsub": True}})

    features = Features(parser)

    expected = not features.use_polling_to_read_tango_attributes
    assert features.use_pubsub_to_read_tango_attributes == expected


def test_polling_is_set_as_the_default_read_mechanism():
    """
    Test to make sure that, in the absence of a config file, polling is set as
    the default mechanism for reading from tango.
    """
    parser = ConfigParser()
    parser.read_dict({})

    features = Features(parser)

    assert features.use_polling_to_read_tango_attributes is True


def test_configparser_strings_are_converted_to_booleans():
    """
    ConfigParser reads everything in as a string, which can lead to some odd
    behaviour when converting 'False' to a boolean. Testing that all possible
    values for False are correctly interpreted.
    """

    for options in ["false", "False", "no", 0]:
        parser = ConfigParser()
        parser.read_dict({"tango": {"read_via_pubsub": options}})

        features = Features(parser)

        assert features.use_pubsub_to_read_tango_attributes is False


def test_can_read_config_file(tmpdir):
    """
    Testing that a specified config file can be read by OET
    """

    filename = tmpdir.mkdir("sub").join("blah.ini")

    parser = ConfigParser()
    parser.add_section("tango")

    parser["tango"]["read_via_pubsub"] = "True"

    with open(filename, "w") as configfile:
        parser.write(configfile)

    features = Features.create_from_config_files(filename)

    assert features.use_polling_to_read_tango_attributes is False


def test_default_config_file_is_packaged():
    """
    Test to make sure that the default config file is packaged.
    Added to catch a bug found during code review.
    """
    assert resource_exists("oet", "oet.ini") is True
