# pylint: disable=protected-access
# - protected-access - tests need to access protected props
"""
Unit tests for the ska_oso_oet.activity.application module.
"""
import time
from unittest import mock as mock

from ska_oso_pdm.entities.common.procedures import (
    FilesystemScript as pdm_FilesystemScript,
)
from ska_oso_pdm.entities.common.procedures import PythonArguments
from ska_oso_pdm.entities.common.sb_definition import SBDefinition
from ska_oso_pdm.generated.models.sb_instance import SBInstance

from ska_oso_oet.activity.application import (
    ActivityCommand,
    ActivityService,
    ActivitySummary,
)
from ska_oso_oet.activity.domain import Activity, ActivityState
from ska_oso_oet.event import topics
from ska_oso_oet.procedure.application import PrepareProcessCommand, StartProcessCommand
from ska_oso_oet.procedure.domain import FileSystemScript, ProcedureInput

from ..test_ui import PubSubHelper


class TestActivityService:
    @mock.patch("ska_oso_oet.activity.application.skuid.fetch_skuid")
    @mock.patch("ska_oso_oet.activity.application.ActivityService.write_sbd_to_file")
    @mock.patch.object(time, "time")
    def test_activityservice_prepare_run(
        self, mock_time_fn, mock_write_fn, mock_skuid_fn
    ):
        mock_pid = 2
        mock_summary = mock.MagicMock(id=mock_pid)
        spec = {
            topics.request.procedure.create: [
                (
                    [topics.procedure.lifecycle.created],
                    dict(result=mock_summary),
                )
            ],
        }
        helper = PubSubHelper(spec)
        mock_state_time = time.time()
        mock_time_fn.return_value = mock_state_time
        mock_write_fn.return_value = "/tmp/sbs/mock_path.json"
        mock_request_id = time.time_ns()
        test_sbi_id = "sbi-1234"
        mock_skuid_fn.return_value = test_sbi_id

        with mock.patch("ska_oso_oet.activity.application.RESTUnitOfWork"):
            pdm_script = pdm_FilesystemScript(path="file:///script/path.py")
            pdm_script.function_args["main"] = PythonArguments(kwargs={})

            activity_service = ActivityService()
            # Mock the ODA context manager
            activity_service._oda.__enter__.return_value = activity_service._oda
            activity_service._oda.sbds.get.return_value = SBDefinition(
                sbd_id="sbd-123", activities={"allocate": pdm_script}
            )

            cmd = ActivityCommand(
                activity_name="allocate",
                sbd_id="sbd-123",
                prepare_only=False,
                create_env=False,
                script_args={
                    "init": ProcedureInput(init_arg="value"),
                    "main": ProcedureInput(main_arg="value"),
                },
            )

            # Run the unit under test
            activity_service.prepare_run_activity(cmd, mock_request_id)

            expected_activity = Activity(
                activity_id=1,
                procedure_id=None,
                activity_name="allocate",
                sbd_id="sbd-123",
                prepare_only=False,
                sbi_id=test_sbi_id,
            )
            expected_sbi = SBInstance(
                sbi_id=test_sbi_id,
                sbd_id="sbd-123",
                runtime_args=PythonArguments(args=[], kwargs={"main_arg": "value"}),
            )
            # Check the SBI is created and persisted
            mock_skuid_fn.assert_called_once()
            activity_service._oda.sbis.add.assert_called_once_with(  # pylint: disable=E1101
                expected_sbi
            )

            # Check that the activity is recorded within the ActivityService
            # as expected
            assert activity_service.activities[1] == expected_activity
            assert activity_service.script_args[1] == {
                "init": ProcedureInput(init_arg="value"),
                "main": ProcedureInput(
                    main_arg="value",
                    sb_json="/tmp/sbs/mock_path.json",
                    sbi_id=test_sbi_id,
                ),
            }
            assert len(activity_service.states[1]) == 1
            assert activity_service.states[1][0] == (
                ActivityState.TODO,
                mock_state_time,
            )

            # Check that a message requesting procedure creation has been sent
            expected_prep_cmd = PrepareProcessCommand(
                script=FileSystemScript(script_uri=pdm_script.path),
                init_args=ProcedureInput(init_arg="value"),
            )
            assert len(helper.messages_on_topic(topics.request.procedure.create)) == 1

            prep_cmd = helper.messages_on_topic(topics.request.procedure.create)[0][
                "cmd"
            ]
            assert prep_cmd == expected_prep_cmd

    @mock.patch("ska_oso_oet.activity.application.skuid.fetch_skuid")
    @mock.patch("ska_oso_oet.activity.application.ActivityService.write_sbd_to_file")
    def test_activityservice_prepare_run_adds_function_args(
        self, mock_write_fn, mock_skuid_fn
    ):
        test_sbi_id = "sbi-123"
        mock_skuid_fn.return_value = test_sbi_id
        helper = PubSubHelper()
        mock_write_fn.return_value = "/tmp/sbs/mock_path.json"
        with mock.patch(
            "ska_oso_oet.activity.application.RESTUnitOfWork",
        ):
            pdm_script = pdm_FilesystemScript(path="file:///script/path.py")
            activity_service = ActivityService()
            # Mock the ODA context manager
            activity_service._oda.__enter__.return_value = activity_service._oda
            activity_service._oda.sbds.get.return_value = SBDefinition(
                sbd_id="sbd-123", activities={"allocate": pdm_script}
            )

            init_args = ProcedureInput("1", a="b")
            main_args = ProcedureInput("2", c="d")
            cmd = ActivityCommand(
                activity_name="allocate",
                sbd_id="sbd-123",
                prepare_only=False,
                create_env=False,
                script_args={"init": init_args, "main": main_args},
            )

            # Run the unit under test
            activity_service.prepare_run_activity(cmd, 123)

            expected_prep_cmd = PrepareProcessCommand(
                script=FileSystemScript(script_uri=pdm_script.path),
                init_args=init_args,
            )
            assert helper.topic_list == [topics.request.procedure.create]

            # Check that a message requesting procedure creation has been sent
            assert len(helper.messages_on_topic(topics.request.procedure.create)) == 1

            # Check that the prepare command contains what we expect it to contain
            prep_cmd = helper.messages_on_topic(topics.request.procedure.create)[0][
                "cmd"
            ]
            assert prep_cmd == expected_prep_cmd

            assert activity_service.script_args[1] == {
                "init": ProcedureInput("1", a="b"),
                "main": ProcedureInput(
                    "2", c="d", sb_json="/tmp/sbs/mock_path.json", sbi_id=test_sbi_id
                ),
            }

    def test_activityservice_complete_run(self):
        test_sbi_id = "sbi-1234"
        mock_pid = 2
        mock_aid = 1
        mock_summary = mock.MagicMock(id=mock_pid)
        helper = PubSubHelper()

        mock_request_time = time.time_ns()

        expected_summary = ActivitySummary(
            id=mock_aid,
            activity_name="allocate",
            pid=mock_pid,
            sbd_id="sbd-123",
            prepare_only=False,
            activity_states=[(ActivityState.TODO, mock_request_time)],
            script_args={"main": ProcedureInput([], {})},
            sbi_id=test_sbi_id,
        )

        activity_service = ActivityService()
        activity_service.request_ids_to_aid[mock_request_time] = mock_aid
        activity_service.activities[mock_aid] = Activity(
            activity_id=1,
            procedure_id=None,
            activity_name="allocate",
            sbd_id="sbd-123",
            prepare_only=False,
            sbi_id=test_sbi_id,
        )
        activity_service.script_args[mock_aid] = {"main": ProcedureInput([], {})}
        activity_service.states[mock_aid] = [(ActivityState.TODO, mock_request_time)]

        summary = activity_service.complete_run_activity(
            mock_summary, mock_request_time
        )

        assert summary == expected_summary

        assert helper.topic_list == [topics.request.procedure.start]

        expected_start_cmd = StartProcessCommand(
            mock_pid,
            fn_name="main",
            run_args=ProcedureInput([], {}),
            force_start=True,
        )

        assert len(helper.messages_on_topic(topics.request.procedure.start)) == 1

        start_cmd = helper.messages_on_topic(topics.request.procedure.start)[0]["cmd"]
        assert start_cmd == expected_start_cmd

    def test_activityservice_complete_prepare_only(self):
        mock_pid = 1
        mock_summary = mock.MagicMock(id=mock_pid)
        helper = PubSubHelper()

        activity_service = ActivityService()
        _ = activity_service.complete_run_activity(mock_summary, 123)

        # Check that the message to start procedure was not sent
        assert len(helper.messages_on_topic(topics.request.procedure.start)) == 0

    def test_activityservice_complete_run_returns_none_for_procedure_without_activity(
        self,
    ):
        """
        If ActivityService.request_ids_to_aid does not contain the request_id, then the Procedure
        is not created from an Activity so the function should return None
        """
        mock_pid = 2
        mock_summary = mock.MagicMock(id=mock_pid)
        helper = PubSubHelper()

        mock_request_time = time.time_ns()

        activity_service = ActivityService()

        result = activity_service.complete_run_activity(mock_summary, mock_request_time)

        assert result is None

        # Check that the message to start procedure was not sent
        assert len(helper.messages_on_topic(topics.request.procedure.start)) == 0

    def test_activityservice_summarise(self):
        sbd_id = "sbd-123"
        sbi_id = "sbi-789"
        activity1 = Activity(
            activity_id=1,
            procedure_id=1,
            activity_name="allocate",
            sbd_id=sbd_id,
            prepare_only=False,
            sbi_id=sbi_id,
        )
        a1_args = {
            "init": ProcedureInput(
                args=[1, "foo", False], kwargs={"foo": "bar", 1: 123}
            ),
            "main": ProcedureInput(args=[], kwargs={"subarray_id": 1}),
        }
        a1_states = [(ActivityState.TODO, time.time())]

        activity2 = Activity(
            activity_id=2,
            procedure_id=2,
            activity_name="observe",
            sbd_id=sbd_id,
            prepare_only=True,
            sbi_id=sbi_id,
        )
        a2_args = {
            "init": ProcedureInput(
                args=[2, "bar", True], kwargs={"foo": "foo", 2: 456}
            ),
            "main": ProcedureInput(args=[], kwargs={"subarray_id": 1}),
        }
        a2_states = [(ActivityState.TODO, time.time() + 1)]

        # Create summary objects we expect from the service
        expected_a1_summary = ActivitySummary(
            id=1,
            pid=1,
            sbd_id=sbd_id,
            activity_name="allocate",
            activity_states=a1_states,
            prepare_only=False,
            script_args=a1_args,
            sbi_id=sbi_id,
        )
        expected_a2_summary = ActivitySummary(
            id=2,
            pid=2,
            sbd_id=sbd_id,
            activity_name="observe",
            activity_states=a2_states,
            prepare_only=True,
            script_args=a2_args,
            sbi_id=sbi_id,
        )

        with mock.patch(
            "ska_oso_oet.activity.application.RESTUnitOfWork",
        ):
            activity_service = ActivityService()

            # Add activities to the service's list of activities, states and arguments
            activity_service.activities = {1: activity1, 2: activity2}
            activity_service.states = {1: a1_states, 2: a2_states}
            activity_service.script_args = {1: a1_args, 2: a2_args}

            summaries = activity_service.summarise([1])
            assert len(summaries) == 1
            assert summaries[0] == expected_a1_summary

            summaries = activity_service.summarise()
            assert len(summaries) == 2
            assert summaries[0] == expected_a1_summary
            assert summaries[1] == expected_a2_summary
