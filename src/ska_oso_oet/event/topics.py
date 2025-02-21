# Relax pylint in the face of some pypubsub requirements. Pypubsub topics use
# msg_src rather than self, and they define a topic hierarchy rather than a
# class hierarchy where implementation is required.
#
# pylint: disable=no-self-argument,too-few-public-methods


class request:
    """
    Root topic for events emitted when a user or system component has made a
    request.
    """

    class procedure:
        """
        Topic for user requests related to procedures.
        """

        class create:
            """
            Emitted when a request to create a procedure is received.
            """

            def msgDataSpec(msg_src, request_id, cmd):
                """
                - msg_src: component from which the request originated
                - request_id: unique identifier for this request
                - cmd: PrepareProcessCommand containing request parameters
                """

        class list:
            """
            Emitted when a request to enumerate all procedures is received.
            """

            def msgDataSpec(msg_src, request_id, pids=None):
                """
                - msg_src: component from which the request originated
                - request_id: unique identifier for this request
                - pids: Procedure IDs to list
                """

        class start:
            """
            Emitted when a request to start procedure execution is received.
            """

            def msgDataSpec(msg_src, request_id, cmd):
                """
                - msg_src: component from which the request originated
                - request_id: unique identifier for this request
                - cmd: StartProcessCommand containing request parameters
                """

        class stop:
            """
            Emitted when a request to stop a procedure is received.
            """

            def msgDataSpec(msg_src, request_id, cmd):
                """
                - msg_src: component from which the request originated
                - request_id: unique identifier for this request
                - cmd: StartProcessCommand containing request parameters
                """

    class activity:
        """
        Topic for user requests related to activities.
        """

        class run:
            """
            Emitted when a request to run an activity is received.
            """

            def msgDataSpec(msg_src, request_id, cmd):
                """
                - msg_src: component from which the request originated
                - request_id: unique identifier for this request
                - cmd: ActivityCommand containing request parameters
                """

        class list:
            """
            Emitted when a request to enumerate all activities is received.
            """

            def msgDataSpec(msg_src, request_id, activity_ids=None):
                """
                - msg_src: component from which the request originated
                - request_id: unique identifier for this request
                - activity_ids: Activity IDs to list.
                """


class procedure:
    """
    Root topic for events related to procedures.
    """

    class lifecycle:
        """
        Topic for events related to procedure lifecycle.
        """

        class statechange:
            """
            Emitted when a procedure status changes.

            To be amalgamated and rationalised with other lifecycle events to
            better handle rerunnable scripts.
            """

            def msgDataSpec(msg_src, new_state):
                """
                - msg_src: component from which the request originated
                - new_state: new state
                """

        class stacktrace:
            """
            Announces cause of a Procedure failure.
            """

            def msgDataSpec(msg_src, stacktrace):
                """
                - msg_src: component from which the request originated
                - stacktrace: stacktrace as a string
                """

        class complete:
            """
            Emitted when a Procedure has completed successfully and is no longer
            available to be called.
            """

            def msgDataSpec(msg_src, request_id, result):
                """
                - msg_src: ID of Procedure that completed
                """

        class created:
            """
            Emitted when a procedure is created, i.e., a script is loaded and
            Python interpreter initialised.
            """

            def msgDataSpec(msg_src, request_id, result):
                """
                - msg_src: component from which the request originated
                - request_id: unique identifier for this request
                - result: ProcedureSummary characterising the created procedure
                """

        class started:
            """
            Emitted when any user function in a procedure is running, i.e., script init is called
            """

            def msgDataSpec(msg_src, request_id, result):
                """
                - msg_src: component from which the request originated
                - request_id: unique identifier for this request
                - result: ProcedureSummary characterising the created procedure
                """

        class stopped:
            """
            Emitted when a procedure stops, e.g., script completes or is aborted.
            """

            def msgDataSpec(msg_src, request_id, result):
                """
                - msg_src: component from which the request originated
                - request_id: unique identifier for this request
                - result: ProcedureSummary characterising the created procedure
                """

        class failed:
            """
            Emitted when a procedure fails.
            """

            def msgDataSpec(msg_src, request_id, result):
                """
                - msg_src: component from which the event originated
                - request_id: unique identifier for this event
                - result: ProcedureSummary characterising the failed procedure
                """

    class pool:
        """
        Topic for events on characterisation of the process pool.
        """

        class list:
            """
            Emitted when current procedures and their status is enumerated.
            """

            def msgDataSpec(msg_src, request_id, result):
                """
                - msg_src: component from which the request originated
                - request_id: unique identifier for this request
                - result: list of ProcedureSummary instances characterising
                          procedures and their states.
                """


class activity:
    """
    Root topic for events related to activities.
    """

    class lifecycle:
        """
        Topic for events related to activity lifecycle.
        """

        class running:
            """
            Emitted when an activity starts running.
            """

            def msgDataSpec(msg_src, request_id, result):
                """
                - msg_src: component from which the request originated
                - request_id: unique identifier for this request
                - result: ActivitySummary characterising the running activity
                """

    class pool:
        """
        Topic for events on characterisation of the activity pool.
        """

        class list:
            """
            Emitted when current activities and their status is enumerated.
            """

            def msgDataSpec(msg_src, request_id, result):
                """
                - msg_src: component from which the request originated
                - request_id: unique identifier for this request
                - result: list of ActivitySummary instances characterising
                          activites and their states.
                """


class sb:
    """
    Root topic for events emitted relating to Scheduling Blocks
    """

    class lifecycle:
        """
        Topic for events related to Scheduling Block lifecycle
        """

        class started:
            """
            Emitted when an observation is started
            """

            def msgDataSpec(msg_src, sbi_id):
                """
                - msg_src: component from which the request originated
                - sbi_id: Scheduling Block Instance ID
                """

        # TODO: Once Activity state management is implemented, send these messages
        #  when activity execution has completed.
        class finished:
            """
            Emitted when an observation is finished
            """

            class succeeded:
                """
                Emitted when an observation is finished successfully
                """

                def msgDataSpec(msg_src, sbi_id):
                    """
                    - msg_src: component from which the request originated
                    - sbi_id: Scheduling Block Instance ID
                    """

            class failed:
                """
                Emitted when an error was encountered during observation execution
                """

                def msgDataSpec(msg_src, sbi_id):
                    """
                    - msg_src: component from which the request originated
                    - sbi_id: Scheduling Block Instance ID
                    """
