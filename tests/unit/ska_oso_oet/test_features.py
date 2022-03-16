"""
Unit tests for the features module
"""
import os
from configparser import ConfigParser
from importlib import resources
from unittest import mock

from ska_oso_oet.features import Features


def test_pubsub_precedence():
    """
    Test that feature flags are set in the expected order:
      1. by environment variable
      2. by ska_oso_oet.ini file
      3. default value set in code
    """
    # get the default value by supplying a parser with no flags set
    parser = ConfigParser()
    default_value = Features(parser).discard_first_event

    # set the flag value in the file to the inverse of the default but leave
    # the environment variable unset. If files take precedence over defaults,
    # we should get this value back.
    file_value = not default_value
    parser.read_dict({"tango": {"discard_first_event": file_value}})
    assert Features(parser).discard_first_event == file_value

    # Finally, run that last test again but with an environment variable set
    # to the inverse of the file value. The feature flag should now return
    # the value of this environment variable.
    env_value = not file_value
    with mock.patch.dict(os.environ, {"OET_DISCARD_FIRST_EVENT": str(env_value)}):
        assert Features(parser).discard_first_event == env_value


def test_pubsub_feature_returns_true_when_enabled_in_file():
    """
    Test to ensure that the 'discard first event' toggle returns 'true' when enabled.
    """
    parser = ConfigParser()
    parser.read_dict({"tango": {"discard_first_event": True}})

    features = Features(parser)
    assert features.discard_first_event is True


def test_discard_first_event_is_enabled_by_default():
    """
    Test to make sure that, in the absence of a config file, polling is set as
    the default mechanism for reading from tango.
    """
    parser = ConfigParser()
    parser.read_dict({})

    features = Features(parser)

    assert features.discard_first_event is True


def test_configparser_strings_are_converted_to_booleans():
    """
    ConfigParser reads everything in as a string, which can lead to some odd
    behaviour when converting 'False' to a boolean. Testing that all possible
    values for False are correctly interpreted.
    """

    for options in ["false", "False", "no", 0]:
        parser = ConfigParser()
        parser.read_dict({"tango": {"discard_first_event": options}})

        features = Features(parser)

        assert features.discard_first_event is False


def test_can_read_config_file(tmpdir):
    """
    Testing that a specified config file can be read by OET
    """

    filename = tmpdir.mkdir("sub").join("blah.ini")

    parser = ConfigParser()
    parser.add_section("tango")

    parser["tango"]["discard_first_event"] = "False"

    with open(filename, "w") as configfile:  # pylint: disable=unspecified-encoding
        parser.write(configfile)

    features = Features.create_from_config_files(filename)

    assert features.discard_first_event is False


def test_default_config_file_is_packaged():
    """
    Test to make sure that the default config file is packaged.
    Added to catch a bug found during code review.
    """
    assert resources.is_resource("ska_oso_oet", "ska_oso_oet.ini")
