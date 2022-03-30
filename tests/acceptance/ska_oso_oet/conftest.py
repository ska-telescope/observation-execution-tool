import os

import pytest
import requests

from .util import ScriptExecutionEnvironment


@pytest.fixture(autouse=True, scope="session")
def setup():
    """
    A setup fixture to check that OET REST server is running and available at
    address defined by OET_REST_URI environment variable.
    """
    oet_rest_uri = os.getenv("OET_REST_URI")
    try:
        resp = requests.get(oet_rest_uri)
    except requests.exceptions.ConnectionError:
        raise Exception(
            "OET REST service not available at %s", oet_rest_uri
        ) from None
    if resp.status_code != 200:
        raise Exception(
            "Invalid response from OET REST service at %s", oet_rest_uri
        )


@pytest.fixture()
def exec_env():
    """
    A fixture to make sure that the same script is tracked throughout the test.
    Keeps track of the script ID and makes sure all commands are run on the
    same script.

    :return exec_env: ScriptExecutionEnvironment for the test
    """
    exec_env = ScriptExecutionEnvironment()
    return exec_env
