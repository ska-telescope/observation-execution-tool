import os

import pytest
import requests
from ska_oso_pdm.sb_definition import SBDefinition

from ...unit.conftest import token
from .util import OET_URL, ScriptExecutionEnvironment


@pytest.fixture(autouse=True, scope="session")
def setup():
    """
    A setup fixture to check that OET REST server is running and available at
    address defined by OET_URL environment variable.
    """
    oet_procedures_rest_uri = f"{OET_URL}/procedures"
    try:
        resp = requests.get(
            oet_procedures_rest_uri,
            timeout=1.0,
            headers={"Authorization": f"Bearer {token}"},
        )
    except requests.exceptions.ConnectionError as e:
        raise IOError(
            f"OET REST service not available at {oet_procedures_rest_uri}"
        ) from e

    if resp.status_code != 200:
        raise IOError(
            f"Invalid {resp.status_code} response from OET REST service at"
            f" {oet_procedures_rest_uri} with body {resp.text}"
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
    with open(path, "r", encoding="utf-8") as fh:
        return SBDefinition.model_validate_json(fh.read())
