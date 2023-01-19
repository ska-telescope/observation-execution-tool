import logging
from os import getenv

from pytest_bdd import given, parsers, scenario, then, when
from ska_db_oda.unit_of_work.restunitofwork import RESTUnitOfWork
from ska_oso_oet_client.activityclient import ActivityAdapter

from .util import test_sbd

LOGGER = logging.getLogger()

KUBE_NAMESPACE = getenv("KUBE_NAMESPACE", "ska-oso-oet")

adapter = ActivityAdapter(f"{getenv('OET_REST_URI')}/activities")


@scenario(
    "features/activity.feature",
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
    test_sbd.sbd_id = "sbi-mvp01-20200325-00002211"
    with oda:
        oda.sbds.add(test_sbd)
        oda.commit()


@when("the OET CLI is used to run the allocate activity on the SBDefinition")
def run_activity():
    adapter.run(
        "allocate",
        "sbi-mvp01-20200325-00002211",
    )


@then(
    parsers.parse("the script should be in state {state} after execution is finished")
)
def procedure_ends_in_expected_state(state, exec_env):
    final_state = exec_env.wait_for_state(state)
    assert final_state == state


@then(parsers.parse("the activity should be in state {state}"))
def activity_ends_in_expected_state(state):
    summaries = adapter.list()
    assert summaries[0].state == state
