

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


class procedure:
    """
    Root topic for events related to procedures.
    """
    class lifecycle:
        """
        Topic for events related to procedure lifecycle.
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
            Emitted when a procedure starts, i.e., script starts execution.
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


class user:
    """
    UNDOCUMENTED: created as parent without specification
    """
    class script:
        """
        UNDOCUMENTED: created as parent without specification
        """
        class announce:
            """
            UNDOCUMENTED: created without spec
            """
            def msgDataSpec(msg_src, msg):
                """
                - msg_src: component from which the request originated
                - msg: user message
                """


class sb:
    """
    Root topic for events emitted relating to Scheduling Blocks
    """
    class lifecycle:
        """
        Topic for events related to Scheduling Block lifecycle
        """
        class allocated:
            """
            Emitted when resources have been allocated within SB execution
            """
            def msgDataSpec(msg_src, sb_id):
                """
                - msg_src: component from which the request originated
                - sb_id: Scheduling Block ID
                """

        class observation:
            """
            Topic for events related to executing an observation within an SB
            """
            class started:
                """
                Emitted when an observation is started
                """
                def msgDataSpec(msg_src, sb_id):
                    """
                    - msg_src: component from which the request originated
                    - sb_id: Scheduling Block ID
                    """
            class finished:
                """
                Emitted when an observation is finished
                """
                class succeeded:
                    """
                    Emitted when an observation is finished successfully
                    """
                    def msgDataSpec(msg_src, sb_id):
                        """
                        - msg_src: component from which the request originated
                        - sb_id: Scheduling Block ID
                        """
                class failed:
                    """
                    Emitted when an error was encountered during observation execution
                    """
                    def msgDataSpec(msg_src, sb_id):
                        """
                        - msg_src: component from which the request originated
                        - sb_id: Scheduling Block ID
                        """


class subarray:
    """
    Root topic for events emitted relating to individual Subarray activites
    """
    class resources:
        """
        Topic for events relating to Subarray resources
        """
        class allocated:
            """
            Emitted when resources have been allocated to a subarray
            """
            def msgDataSpec(msg_src, subarray_id):
                """
                - msg_src: component from which the request originated
                - sb_id: Subarray ID
                """

        class deallocated:
            """
            Emitted when resources have been deallocated from a subarray
            """
            def msgDataSpec(msg_src, subarray_id):
                """
                - msg_src: component from which the request originated
                - sb_id: Subarray ID
                """
    class configured:
        """
        Emitted when subarray has been configured
        """
        def msgDataSpec(msg_src, subarray_id):
            """
            - msg_src: component from which the request originated
            - sb_id: Subarray ID
            """

    class scan:
        """
        Topic for events emitted when a scan is run on subarray
        """
        class started:
            """
            Emitted when a scan is started
            """
            def msgDataSpec(msg_src, subarray_id):
                """
                - msg_src: component from which the request originated
                - sb_id: Subarray ID
                """
        class finished:
            """
            Emitted when a scan is finished
            """
            def msgDataSpec(msg_src, subarray_id):
                """
                - msg_src: component from which the request originated
                - sb_id: Subarray ID
                """

    class fault:
        """
        Topic for events emitted when subarray cannot be reached
        """
        def msgDataSpec(msg_src, subarray_id, error):
            """
            - msg_src: component from which the request originated
            - sb_id: Subarray ID
            - error: Error response received from Subarray
            """


class scan:
    """
    Root topic for events emitted relating to Scans in the context of SB execution
    """
    class lifecycle:
        """
        Topic for events related to SB scan lifecycle
        """
        class configure:
            """
            Emitted when sub-array resources are configured for a scan
            """
            class started:
                """
                Emitted as scan configuration begins.
                """
                def msgDataSpec(msg_src, sb_id, scan_id):
                    """
                    - msg_src: component from which the request originated
                    - sb_id: Scheduling Block ID
                    - scan_id: Scan ID
                    """
            class complete:
                """
                Emitted as scan configuration completes successfully.
                """
                def msgDataSpec(msg_src, sb_id, scan_id):
                    """
                    - msg_src: component from which the request originated
                    - sb_id: Scheduling Block ID
                    - scan_id: Scan ID
                    """
            class failed:
                """
                Emitted if scan configuration fails.
                """
                def msgDataSpec(msg_src, sb_id, scan_id):
                    """
                    - msg_src: component from which the request originated
                    - sb_id: Scheduling Block ID
                    - scan_id: Scan ID
                    """

        class start:
            """
            Emitted when resources have been allocated within SB execution
            """
            def msgDataSpec(msg_src, sb_id):
                """
                - msg_src: component from which the request originated
                - sb_id: Scheduling Block ID
                - scan_id: Scan ID
                """

        class end:
            """
            Emitted when a scan finishes
            """
            class succeeded:
                """
                Emitted when a scan completes successfully
                """
                def msgDataSpec(msg_src, sb_id, scan_id):
                    """
                    - msg_src: component from which the request originated
                    - sb_id: Scheduling Block ID
                    - scan_id: Scan ID
                    """
            class failed:
                """
                Emitted when an error was encountered during a scan
                """
                def msgDataSpec(msg_src, sb_id, scan_id):
                    """
                    - msg_src: component from which the request originated
                    - sb_id: Scheduling Block ID
                    """
