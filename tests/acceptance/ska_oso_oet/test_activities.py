import logging
from os import getenv

from pytest_bdd import given, parsers, scenario, then, when
from ska_db_oda.unit_of_work.restunitofwork import RESTUnitOfWork
from ska_oso_oet_client.activityclient import ActivityAdapter

LOGGER = logging.getLogger()

KUBE_NAMESPACE = getenv("KUBE_NAMESPACE", "ska-oso-oet")

adapter = ActivityAdapter(f"{getenv('OET_REST_URI')}/activities")


@scenario(
    "features/activity.feature",
    "Run an Activity, with SB retrieval from the ODA",
)
def test_activity_with_script_requiring_sb():
    pass


@scenario(
    "features/activity.feature",
    "Run an Activity with the prepare_only flag, SB retrieval from the ODA",
)
def test_activity_prepare_only():
    pass


@scenario(
    "features/activity.feature",
    "Run an Activity, with script args that cause an error",
)
def test_activity_with_raise_msg_kwarg():
    pass


@given(
    parsers.parse(
        "an SBDefinition {sbd_id} exists in the ODA with script {script} in the"
        " {activity_name} activity"
    )
)
def create_sbd(sbd_id, script, activity_name, test_sbd):
    oda = RESTUnitOfWork()
    test_sbd.sbd_id = sbd_id
    test_sbd.activities[activity_name].path = script
    with oda:
        try:
            existing_sbd = oda.sbds.get(test_sbd.sbd_id)
            test_sbd.metadata.version = existing_sbd.metadata.version
        except KeyError:
            # sbd_id doesn't exist in ODA so no need to worry about versions
            pass
        oda.sbds.add(test_sbd)
        oda.commit()


@when(
    parsers.parse(
        "the OET CLI is used to run the {activity_name} activity on the SBDefinition"
        " {sbd_id}"
    )
)
def run_activity(activity_name, sbd_id):
    adapter.run(
        activity_name,
        sbd_id,
    )


@when(
    parsers.parse(
        "the OET CLI is used to run the {activity_name} activity with the prepare_only"
        " flag on the SBDefinition {sbd_id}"
    )
)
def run_activity_prepare_only(activity_name, sbd_id):
    adapter.run(activity_name, sbd_id, prepare_only=True)


@when(
    parsers.parse(
        "the OET CLI is used to run the {activity_name} activity with {kwarg}={value}"
        " on the SBDefinition {sbd_id}"
    )
)
def run_activity_with_kwarg(activity_name, kwarg, value, sbd_id):
    adapter.run(activity_name, sbd_id, script_args={"main": {"kwargs": {kwarg: value}}})


@then(
    parsers.parse("the script should be in state {state} after execution is finished")
)
def procedure_ends_in_expected_state(state, exec_env):
    final_state = exec_env.wait_for_state(state)
    assert final_state == state


@then(parsers.parse("the activity should be in state {state}"))
def activity_ends_in_expected_state(state):
    summaries = adapter.list()
    assert summaries[-1].state == state
