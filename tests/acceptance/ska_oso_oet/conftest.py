import os

import pytest
import requests
from ska_oso_pdm.entities.common.sb_definition import SBDefinition
from ska_oso_pdm.schemas import CODEC

from .util import ScriptExecutionEnvironment


@pytest.fixture(autouse=True, scope="session")
def setup():
    """
    A setup fixture to check that OET REST server is running and available at
    address defined by OET_REST_URI environment variable.
    """
    oet_procedures_rest_uri = f"{os.getenv('OET_REST_URI')}/procedures"
    try:
        resp = requests.get(oet_procedures_rest_uri, timeout=1.0)
    except requests.exceptions.ConnectionError as e:
        raise IOError(
            f"OET REST service not available at {oet_procedures_rest_uri}"
        ) from e

    if resp.status_code != 200:
        raise IOError(
            f"Invalid response from OET REST service at {oet_procedures_rest_uri}"
        )


@pytest.fixture(name="exec_env")
def fixture_exec_env():
    """
    A fixture to make sure that the same script is tracked throughout the test.
    Keeps track of the script ID and makes sure all commands are run on the
    same script.

    :return exec_env: ScriptExecutionEnvironment for the test
    """
    exec_env = ScriptExecutionEnvironment()
    return exec_env


@pytest.fixture
def test_sbd() -> SBDefinition:
    cwd, _ = os.path.split(__file__)
    path = os.path.join(cwd, "scripts/testfile_sample_mid_sb.json")
    return CODEC.load_from_file(SBDefinition, path)
