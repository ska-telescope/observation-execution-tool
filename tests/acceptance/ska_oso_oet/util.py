# BTN-1394
import logging
import os
import subprocess
import time
import typing

from ska_oso_oet.procedure.application.restclient import RestAdapter

LOGGER = logging.getLogger(__name__)

REST_ADAPTER = RestAdapter(os.getenv("OET_REST_URI"))


if typing.TYPE_CHECKING:
    from ska_oso_oet.procedure.application.restclient import ProcedureSummary


class ScriptExecutionError(Exception):
    pass


class ScriptExecutionEnvironment:
    def __init__(self):
        self.script_id = None
        self.script_uri = None

    def create(self, script_uri: str):
        LOGGER.debug("Setting script ID for script: %s", script_uri)
        if self.script_id:
            raise ScriptExecutionError(
                f"Script already defined for test run: {self.script_uri}"
            )
        summary: "ProcedureSummary" = REST_ADAPTER.create(
            script_uri=script_uri, init_args={"kwargs": {"subarray_id": 1}}
        )
        LOGGER.debug("New script ID: %s", summary.id)
        self.script_id = summary.id
        self.script_uri = summary.script["script_uri"]

    def run_oet_command(self, cmd: str, *args):
        args = list(args)
        if cmd == "start":
            # Set --listen flag to False on start command, otherwise we would need
            # to Ctrl+C to exit the command
            args.append("--listen=False")
            # Add process ID to start command to make sure correct script is started
            args.append(f"--pid={self.script_id}")
        LOGGER.debug("Executing OET command '%s' with args %s", cmd, args)
        result = subprocess.run(
            ["oet", cmd, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        output = result.stdout.decode("utf-8")
        return output

    def wait_for_state(self, exp_state, timeout: int = 60):
        t = timeout
        LOGGER.debug("Waiting for state %s", exp_state)
        while t > 0:
            state = self.get_script_state()
            if state == exp_state:
                return state
            time.sleep(1)
            t -= 1

        state = self.get_script_state()
        msg = (
            f"Timeout (> {timeout} seconds) waiting for state {exp_state}, "
            f"final state {state}"
        )
        raise ScriptExecutionError(msg)

    def get_script_state(self):
        task = self._update_script()
        return task.state

    def _update_script(self):
        task = REST_ADAPTER.list(self.script_id)
        if task:
            return task[0]
        return None
