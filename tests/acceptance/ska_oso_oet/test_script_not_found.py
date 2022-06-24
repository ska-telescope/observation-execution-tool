# BTN-1394
from pytest_bdd import given, parsers, scenario, then, when


@scenario("features/script_not_found.feature", "File does not exist")
def test_script_not_found():
    pass


@given(parsers.parse("file {file} does not exist"))
def file_does_not_exist(file):  # pylint: disable=unused-argument
    pass


@when(
    parsers.parse("the user runs oet create {file} command"),
)
def run_create_command(file, exec_env):
    exec_env.create(file)


@then(
    parsers.parse(
        "the script should be in state {state} after initialisation is finished"
    )
)
def execution_ends_in_expected_state(state, exec_env):
    final_state = exec_env.wait_for_state(state)
    assert final_state == state


@then(parsers.parse("oet describe should show stacktrace with strings {error_strings}"))
def error_returned(error_strings, exec_env):
    response = exec_env.run_oet_command("describe")
    assert all([e in response for e in error_strings.split(", ")])
