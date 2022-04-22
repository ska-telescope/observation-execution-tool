from pytest_bdd import given, parsers, scenario, then, when


@scenario("features/script_not_found.feature", "File does not exist")
def test_script_not_found():
    pass


@given(parsers.parse("file {file} does not exist"))
def file_does_not_exist(file):  # pylint: disable=unused-argument
    pass


@when(
    parsers.parse("the user runs oet create {file} command"),
    target_fixture="response",
)
def run_create_command(file, exec_env):
    response = exec_env.run_oet_command("create", file)
    return response


@then(parsers.parse("the OET returns an {error}"))
def error_returned(response, error):
    assert error in response
