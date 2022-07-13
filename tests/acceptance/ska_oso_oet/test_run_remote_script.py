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


@scenario(
    "features/run_remote_script.feature",
    "Script creation on default environment fails when creating a script from git",
)
def test_remote_script_fail():
    pass


@scenario(
    "features/run_remote_script.feature",
    "User creates a script with non-default dependencies from git using OET",
)
def test_remote_script_run():
    pass


@given(
    parsers.parse(
        "git repository {repo} and script {script} within the repository exist"
    )
)
def git_repo_and_script_exist(repo, script):
    # Confirming that the given git repository and the script within that repository exist
    # requires connecting to the OET kubernetes pod and so has been left as future work for
    # now until an efficient way to achieve this is figured out.
    pass


@when(parsers.parse("the user runs oet create with arguments {args}"))
def execute_run_command(args, exec_env):
    args = args.split()
    exec_env.run_oet_command("create", *args)


@then(parsers.parse("the script should be in state READY after execution is finished"))
def execution_ends_in_expected_state(exec_env):
    final_state = exec_env.wait_for_state("READY", timeout=300)
    assert final_state == "READY"


@then(parsers.parse("the script should go to state {state}"))
def execution_ends_in_expected_state(state, exec_env):
    final_state = exec_env.wait_for_state(state)
    assert final_state == state


@then(parsers.parse("oet describe should show stacktrace with {error}"))
def execution_ends_in_expected_state(error, exec_env):
    response = exec_env.run_oet_command("describe")
    assert error in response
