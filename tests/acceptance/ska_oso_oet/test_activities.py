import logging
from datetime import datetime
from os import getenv

from pytest_bdd import given, parsers, scenario, then, when
from ska_db_oda.unit_of_work.restunitofwork import RESTUnitOfWork
from ska_oso_oet_client.activityclient import ActivityAdapter

from .util import test_sbd

LOGGER = logging.getLogger()

KUBE_NAMESPACE = getenv("KUBE_NAMESPACE", "ska-oso-oet")


@scenario(
    "features/oda_connection.feature",
    "Activity driven execution of the OET, with SB retrieval from the ODA",
)
def test_activity():
    pass


@given(
    "an SBDefinition exists in the ODA with a filesystem success.py script in the test"
    " activity"
)
def create_sbd():
    oda = RESTUnitOfWork()
    test_sbd.sbd_id = f"sbd-mvp01-{datetime.now().timestamp()}"
    with oda:
        oda.sbds.add(test_sbd)
        oda.commit()


@when("the OET CLI is used to run the allocate activity on the SBDefinition")
def run_activity():
    try:
        adapter = ActivityAdapter(
            "http://192.168.64.9/ska-oso-oet/ska-oso-oet/api/v1.0/activities"
        )
        adapter.run(
            "allocate",
            "sbi-mvp01-20200325-00001",
        )
    except Exception as err:  # pylint: disable=broad-except
        print(f"Ignoring Exception for now {err}")


@then(
    parsers.parse("the script should be in state {state} after execution is finished")
)
def execution_ends_in_expected_state(state, exec_env):
    final_state = exec_env.wait_for_state(state)
    assert final_state == state
