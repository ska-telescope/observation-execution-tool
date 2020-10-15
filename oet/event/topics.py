

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

    """
    class lifecycle:
        """

        """
        class allocated:
            """

            """
            def msgDataSpec(msg_src, sb_id):
                """
                - msg_src: component from which the request originated
                - sb_id: Scheduling Block ID
                """

        class observation:
            """

            """
            class started:
                """

                """
                def msgDataSpec(msg_src, sb_id):
                    """
                    - msg_src: component from which the request originated
                    - sb_id: Scheduling Block ID
                    """
            class finished:
                """

                """
                class succeeded:
                    """

                    """
                    def msgDataSpec(msg_src, sb_id):
                        """
                        - msg_src: component from which the request originated
                        - sb_id: Scheduling Block ID
                        """
                class failed:
                    """

                    """
                    def msgDataSpec(msg_src, sb_id):
                        """
                        - msg_src: component from which the request originated
                        - sb_id: Scheduling Block ID
                        """


class subarray:
    """

    """
    class resources:
        """

        """
        class allocated:
            """

            """
            def msgDataSpec(msg_src, subarray_id):
                """
                - msg_src: component from which the request originated
                - sb_id: Subarray ID
                """

        class deallocated:
            """

            """
            def msgDataSpec(msg_src, subarray_id):
                """
                - msg_src: component from which the request originated
                - sb_id: Subarray ID
                """
    class configured:
        """

        """
        def msgDataSpec(msg_src, subarray_id):
            """
            - msg_src: component from which the request originated
            - sb_id: Subarray ID
            """

    class scan:
        """

        """
        class started:
            """

            """
            def msgDataSpec(msg_src, subarray_id):
                """
                - msg_src: component from which the request originated
                - sb_id: Subarray ID
                """
        class finished:
            """

            """
            def msgDataSpec(msg_src, subarray_id):
                """
                - msg_src: component from which the request originated
                - sb_id: Subarray ID
                """

    class fault:
        """

        """
        def msgDataSpec(msg_src, subarray_id):
            """
            - msg_src: component from which the request originated
            - sb_id: Subarray ID
            """
