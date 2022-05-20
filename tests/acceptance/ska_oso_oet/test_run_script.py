import logging

import pytest
from pytest_bdd import given, parsers, scenario, then, when

LOGGER = logging.getLogger()


@pytest.fixture(autouse=True)
def teardown(request, exec_env):
    """
    A fixture to stop the script if still running at the end of the test.
    """

    def fin():
        if exec_env.get_script_state() == "RUNNING":
            resp = exec_env.run_oet_command("stop", "--run_abort=False")
            assert "Successfully stopped" in resp

    request.addfinalizer(fin)


@scenario("features/run_script.feature", "User runs a script using OET")
def test_script_run():
    pass


@given(parsers.parse("script {script} has been created"))
def create_script(script, exec_env):
    exec_env.create(script)


@when(parsers.parse("the user runs oet start command"))
def execute_run_command(exec_env):
    output = exec_env.run_oet_command("start")
    assert "READY" in output


@then(
    parsers.parse("the script should be in state {state} after execution is finished")
)
def execution_ends_in_expected_state(state, exec_env):
    final_state = exec_env.wait_for_state(state)
    assert final_state == state
    assert False


@scenario(
    "features/run_script.feature",
    "OET stays responsive when script is running",
)
def test_oet_responsiveness():
    pass


@when(parsers.parse("script {file} is running"))
def script_is_running(exec_env):
    exec_env.run_oet_command("start")
    state = exec_env.wait_for_state("RUNNING")
    assert state == "RUNNING"


@then(parsers.parse("the oet list command response shows {file} is running"))
def error_returned(file, exec_env):
    response = exec_env.run_oet_command("list")
    assert file in response

    state = exec_env.get_script_state()
    assert state == "RUNNING"
