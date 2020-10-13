import enum


class EventTopic(enum.Enum):
    def __getattr__(self, item):
        if item != '_value_':
            return getattr(self.value, item)
        raise AttributeError


class Procedure(EventTopic):
    """
    Topic for events related to Python scripting
    """
    class Request(EventTopic):
        """
        Topic for requests to control Python scripting

        Message data
        request_id: Unique identifier for request
        cmd: Command to send with request

        Message example
        pub.sendMessage('procedure.request.create', request_id=1234, cmd=PrepareProcessCommand)
        """
        Create = enum.auto()
        Start = enum.auto()
        Stop = enum.auto()

        def __str__(self):
            return 'procedure.request.' + self.name.lower()

    class Pool(EventTopic):
        """
        Topic for events related to inspecting procedures.

        Message data
        request_id: Unique identifier for request
        procedures: List of existing Procedures

        Message example
        pub.sendMessage('procedure.pool.list', request_id=1234, procedures=List[ProcedureSummary])
        """
        List = enum.auto()

        def __str__(self):
            return 'procedure.pool.' + self.name.lower()

    class Lifecycle(EventTopic):
        """
        Topic for events related to changes in Procedure state.

        Message data
        request_id: Unique identifier for request
        procedure: Updated procedure

        Message example
        pub.sendMessage('procedure.lifecycle.created', request_id=1234, procedure=ProcedureSummary)
        """
        Created = enum.auto()
        Started = enum.auto()
        Finished = enum.auto()

        def __str__(self):
            return 'procedure.lifecycle.' + self.name.lower()


class SB(EventTopic):
    """
    Topic for events related to Scheduling Blocks
    """
    class Lifecycle(EventTopic):
        """
        Topic for events related to changes in Scheduling Block state.
        """
        Allocated = enum.auto()

        class Observation(EventTopic):
            """
            Topic for events related to changes in observation executed within
            a Scheduling Block.
            """
            Started = enum.auto()
            Finished = enum.auto()

            def __str__(self):
                return 'sb.lifecycle.observation' + self.name.lower()

        def __str__(self):
            return 'sb.lifecycle.' + self.name.lower()


class Subarray(EventTopic):
    """
    Topic for events related to Subarray commands
    """
    Configured = enum.auto()

    class Resources(EventTopic):
        """
        Topic for events related to changes in Subarray resources.
        """
        Allocated = enum.auto()
        Deallocated = enum.auto()

        def __str__(self):
            return 'subarray.resources.' + self.name.lower()

    class Scan(EventTopic):
        """
        Topic for events related to Subarray scan execution.
        """
        Started = enum.auto()
        Stopped = enum.auto()

        def __str__(self):
            return 'subarray.scan.' + self.name.lower()

    def __str__(self):
        return 'subarray.' + self.name.lower()


