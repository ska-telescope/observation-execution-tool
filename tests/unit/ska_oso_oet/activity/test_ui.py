from http import HTTPStatus

from ska_oso_oet.activity.application import ActivityCommand, ActivitySummary
from ska_oso_oet.activity.domain import ActivityState
from ska_oso_oet.event import topics
from ska_oso_oet.procedure.domain import ProcedureInput
from tests.unit.conftest import ACTIVITIES_ENDPOINT

from ..test_ui import PubSubHelper

ACTIVITY_REQUEST = {
    "sbd_id": "sbi-001",
    "activity_name": "allocate",
    "script_args": {"main": {"args": [1], "kwargs": {"subarray_id": "42"}}},
    "prepare_only": False,
}
ACTIVITY_SUMMARY = ActivitySummary(
    id=1,
    pid=123,
    sbd_id="sbd-mvp01-20220923-00001",
    activity_name="allocate",
    prepare_only=False,
    script_args={},
    activity_states=[(ActivityState.TODO, 123)],
    sbi_id="sbi-123",
)


def assert_json_equal_to_activity_summary(summary: ActivitySummary, summary_json: dict):
    """
    Helper function to compare JSON against a reference ActivitySummary
    instance. An assertion error will be raised if the JSON does not match.

    :param summary: reference ActivitySummary instance
    :param summary_json: JSON for the ProcedureSummary
    """
    assert summary_json["uri"] == f"http://localhost/{ACTIVITIES_ENDPOINT}/{summary.id}"
    assert summary_json["procedure_id"] == summary.pid
    assert summary_json["sbd_id"] == summary.sbd_id
    assert summary_json["activity_name"] == summary.activity_name
    assert summary_json["prepare_only"] == summary.prepare_only
    assert summary_json["sbi_id"] == summary.sbi_id


def test_get_activities_with_no_activities_present_returns_empty_list(client):
    """
    Verify that listing resources returns an empty response when no activities
    have been registered
    """
    spec = {
        topics.request.activity.list: [([topics.activity.pool.list], dict(result=[]))],
    }
    _ = PubSubHelper(spec)

    response = client.get(ACTIVITIES_ENDPOINT)

    assert response.json() == []


def test_get_activities_returns_expected_summaries(client):
    """
    Test that listing activities resources returns the expected JSON payload
    """
    spec = {
        topics.request.activity.list: [
            ([topics.activity.pool.list], dict(result=[ACTIVITY_SUMMARY]))
        ],
    }
    _ = PubSubHelper(spec)

    response = client.get(ACTIVITIES_ENDPOINT)
    assert response.status_code == 200
    response_json = response.json()
    assert len(response_json) == 1
    assert_json_equal_to_activity_summary(ACTIVITY_SUMMARY, response_json[0])


def test_get_activity_by_id(client):
    """
    Verify that getting a resource by ID returns the expected JSON payload
    """
    spec = {
        topics.request.activity.list: [
            ([topics.activity.pool.list], dict(result=[ACTIVITY_SUMMARY]))
        ],
    }
    _ = PubSubHelper(spec)

    response = client.get(f"{ACTIVITIES_ENDPOINT}/{ACTIVITY_SUMMARY.id}")
    assert response.status_code == HTTPStatus.OK

    response_json = response.json()
    assert_json_equal_to_activity_summary(ACTIVITY_SUMMARY, response_json)


def test_get_activity_gives_404_for_invalid_id(client):
    """
    Verify that requesting an invalid resource returns an error.
    """
    # empty list as response shows that ID not found when trying to retrieve
    # activity
    spec = {
        topics.request.activity.list: [([topics.activity.pool.list], dict(result=[]))],
    }
    _ = PubSubHelper(spec)

    response = client.get(f"{ACTIVITIES_ENDPOINT}/1")
    assert response.status_code == HTTPStatus.NOT_FOUND

    response_json = response.json()["detail"]  # TODO
    assert response_json == {
        "type": "ResourceNotFound",
        "Message": "No information available for ID=1",
    }


def test_successful_post_to_activities_endpoint_returns_ok_http_status(client):
    """
    Verify that creating a new Activity returns the OK HTTP status code
    """
    spec = {
        topics.request.activity.run: [
            ([topics.activity.lifecycle.running], dict(result=ACTIVITY_SUMMARY))
        ],
    }
    _ = PubSubHelper(spec)

    response = client.post(ACTIVITIES_ENDPOINT, json=ACTIVITY_REQUEST)
    assert response.status_code == HTTPStatus.CREATED


def test_successful_post_to_activities_endpoint_returns_summary_in_response(client):
    """
    Verify that posting a new Activity returns the expected JSON payload:
    a summary of the created Procedure.
    """
    spec = {
        topics.request.activity.run: [
            ([topics.activity.lifecycle.running], dict(result=ACTIVITY_SUMMARY))
        ],
    }
    helper = PubSubHelper(spec)

    response = client.post(ACTIVITIES_ENDPOINT, json=ACTIVITY_REQUEST)
    response_json = response.json()

    cmd: ActivityCommand = helper.messages_on_topic(topics.request.activity.run)[0][
        "cmd"
    ]

    assert cmd.script_args == {"main": ProcedureInput(1, subarray_id="42")}

    assert_json_equal_to_activity_summary(ACTIVITY_SUMMARY, response_json)
