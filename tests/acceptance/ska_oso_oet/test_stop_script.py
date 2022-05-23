from pytest_bdd import given, parsers, scenario, then, when


@scenario("features/stop_script.feature", "Stop script execution")
def test_script_not_found():
    pass


@given(parsers.parse("script {file} is running"))
def script_is_running(file, exec_env):
    exec_env.create(file)
    exec_env.run_oet_command("start")
    state = exec_env.wait_for_state("RUNNING")
    assert state == "RUNNING"


@when(parsers.parse("the user runs oet stop command"))
def run_stop_command(exec_env):
    exec_env.run_oet_command("stop", "--run_abort=False")


@then(parsers.parse("the script {file} status is STOPPED"))
def error_returned(exec_env):
    state = exec_env.get_script_state()
    assert state == "STOPPED"
