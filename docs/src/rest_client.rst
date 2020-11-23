.. _rest-client:

***********
REST Client
***********

SKA observations will be controlled by ‘Procedures’. Each 'Procedure' 
comprises a Python script and a set of arguments, some of which will be 
set when the script is loaded and some at run-time. 

The management of 'Procedures' and the processes which execute them is 
handled by the :doc:`rest_server`, which implements the methods 
described in the :doc:`rest_api`. The :doc:`rest_server` lets the user:

* Load requested Procedure scripts with initialization arguments and 
  have them ready for execution.
* When required, pass run-time arguments to a script and start a process 
  executing it.

Aborting script execution is not required in this PI.

The REST Client provides a command line interface (CLI) through which
the user can communicate with the :doc:`rest_server` remotely.  The
address of the remote REST server can be specified at the command line
via the ``server-url`` argument, or set session-wide by setting the
``OET_REST_URI`` environment variable, e.g.,::

  export OET_REST_URI=http://my-rest-service:5000/api/v1.0/procedures

By default, the client assumes it is operating within a SKAMPI environment
and attempts to connect to a REST server using the default REST service name
of http://oet-rest:5000/api/v1.0/procedures. If running the OET
client within SKAMPI via the oet-ssh or oet-jupyter services, the
``OET_REST_URI`` variable is automatically set.

The methods available through the REST Client map closely to the
:doc:`rest_api` of the server and are described below.

+--------------------+---------------+--------------------------------------------+-------------------------------------+
| REST Client Method | Parameters    | Default                                    | Description                         |
+====================+===============+============================================+=====================================+
| create             | server-url    | See note above                             | **Prepare a new procedure**         |
|                    +---------------+--------------------------------------------+                                     |
|                    | script-uri    | None                                       | Load the requested script and       |
|                    +---------------+--------------------------------------------+ prepare it for execution.           |
|                    | args          | None                                       |                                     |
|                    +---------------+--------------------------------------------+ Arguments provided here are passed  |
|                    | kwargs        | --subarray_id=1                            | to the script init function, if     |
|                    |               |                                            | defined                             |
|                    |               |                                            |                                     |
|                    |               |                                            | OET maintains record of 10 newest   |
|                    |               |                                            | scripts which means creating 11th   |
|                    |               |                                            | script will remove the oldest       |
|                    |               |                                            | script from the record.             |
+--------------------+---------------+--------------------------------------------+-------------------------------------+
| list               | server-url    | See note above                             | **List procedures**                 |
|                    +---------------+--------------------------------------------+-------------------------------------+
|                    | pid           | None                                       | Return info on the collection of 10 |
|                    |               |                                            | newest procedures, or info on the   |
|                    |               |                                            | one specified by process ID (pid)   |
+--------------------+---------------+--------------------------------------------+-------------------------------------+
| start              | server-url    | See note above                             | **Start a Procedure Executing**     |
|                    +---------------+--------------------------------------------+                                     |
|                    | pid           | None                                       | Start a process executing           |
|                    +---------------+--------------------------------------------+ the procedure specified by process  |
|                    | args          | None                                       | ID (pid) or, if none is specified   |
|                    +---------------+--------------------------------------------+ start the last one loaded.          |
|                    | kwargs        | None                                       |                                     |
|                    |               |                                            | Only one procedure can be executing |
|                    |               |                                            | at any time                         |
+--------------------+---------------+--------------------------------------------+-------------------------------------+
| stop               | server-url    | See note above                             | **Stop Procedure Execution**        |
|                    +---------------+--------------------------------------------+                                     |
|                    | pid           | None                                       | Stop a running process executing    |
|                    +---------------+--------------------------------------------+ the procedure specified by process  |
|                    | run_abort     | True                                       | ID (pid) or, if none is specified,  |
|                    |               |                                            | stop the currently running process. |
|                    |               |                                            |                                     |
|                    |               |                                            | If run_abort flag is True, OET will |
|                    |               |                                            | send Abort command to the SubArray  |
|                    |               |                                            | as part of script termination.      |
+--------------------+---------------+--------------------------------------------+-------------------------------------+
| describe           | server-url    | See note above                             | **Investigate a procedure**         |
|                    +---------------+--------------------------------------------+                                     |
|                    | pid           | None                                       | Displays the call arguments, state  |
|                    |               |                                            | history and, if the procedure       |
|                    |               |                                            | failed, the stack trace of a        |
|                    |               |                                            | specified process ID (pid). If no   |
|                    |               |                                            | pid is specified describe the last  | 
|                    |               |                                            | process created.                    |
+--------------------+---------------+--------------------------------------------+-------------------------------------+
| Listen             | server-url    | http://oet-rest:5000/api/v1.0/stream       | **Get real times scripts events**   |
|                    +---------------+--------------------------------------------+                                     |
|                    |               |                                            | Get a real time delivery of events  |
|                    |               |                                            | published by oet scripts            |
|                    |               |                                            |                                     |
|                    |               |                                            |                                     |
|                    |               |                                            |                                     |
|                    |               |                                            |                                     |
+--------------------+---------------+--------------------------------------------+-------------------------------------+

In the table 'args' refers to parameters specified by position on the command line, 'kwargs' to
those specified by name e.g. --myparam=12.

Help Information
----------------
General help information can be obtained by typing the command: ::

  $ oet

Detailed help information for specific commands is also available e.g.::

  $ oet create --help

Examples
--------

This section runs through an example session in which we will
load two new 'Procedures' and then run one of them.
First we load the procedures: ::

  $ oet create file://test.py 'hello' --verbose=true

which will generate the output: ::

    ID  Script           Creation time        State
  ----  ---------------  -------------------  -------
     1  file://test.py   2020-09-30 10:30:12  CREATED

Note the use of both positional and keyword/value arguments for the
procedure on the command line.
Now create a second procedure: ::

  $ oet create file://test2.py 'goodbye'

giving: ::

   ID   Script           Creation time        State
  ----  ---------------  -------------------  -------
    2  file://test2.py  2020-09-30 10:35:12  CREATED

We can check the state of the procedures currently loaded by: ::

  $ oet list

giving: ::

   ID   Script           Creation time        State
  ----  ---------------  -------------------  -------
     1  file://test.py   2020-09-30 10:30:12  CREATED
     2  file://test2.py  2020-09-30 10:35:12  CREATED

Alternatively, we could check the state of procedure 2 by typing: ::

  $ oet list --pid=2

giving: ::

   ID   Script           Creation time        State
  ----  ---------------  -------------------  -------
    2   file://test2.py  2020-09-30 10:35:12  CREATED

Now that we have our procedures loaded we can start one of them running.
At this point we supply the index number of the procedure to run, and
some runtime arguments to pass to it if required. ::

  $ oet start --pid=2 'bob' --simulate=false
 
giving: ::

    ID   Script           Creation time        State
  ----  ---------------  -------------------  -------
    2   file://test2.py  2020-09-30 10:35:12  RUNNING

A 'list' command will give the same information: ::

  $ oet list

giving: ::

    ID   Script           Creation time        State
  ----  ---------------  -------------------  -------
     1  file://test.py   2020-09-30 10:30:12  CREATED
     2  file://test2.py  2020-09-30 10:35:12  RUNNING

A 'describe' command will give further detail on a procedure, no
matter its state.::
 
 $oet describe --pid=2

giving: ::

    ID  Script           URI
  ----  ---------------  ----------------------------------------- 
     2  file://test2.py  http://0.0.0.0:5000/api/v1.0/procedures/2 
 
  Time                        State
  --------------------------  -------
  2020-09-30 10:19:38.646475  CREATED
  2020-09-30 10:35:12.605270  RUNNING
  
  Method    Arguments    Keyword Arguments
  --------  -----------  -------------------
  init      []           {'subarray_id': 1}
  run       []           {}

If the procedure failed, then the stack trace will also be displayed.

A 'listen' command will give the real time delivery of oet events published by scripts: ::

  $ oet listen

giving: ::

    event: request.procedure.list
    data: args=() kwargs={'msg_src': 'FlaskWorker', 'request_id': 1604056049.4846392, 'pids': None}

    event: procedure.pool.list
    data: args=() kwargs={'msg_src': 'SESWorker', 'request_id': 1604056049.4846392, 'result': []}

    event: request.procedure.create
    data: args=() kwargs={'msg_src': 'FlaskWorker', 'request_id': 1604056247.0666442, 'cmd': PrepareProcessCommand(script_uri='file://scripts/eventbus.py', init_args=<ProcedureInput(, subarray_id=1)>)}

    event: procedure.lifecycle.created
    data: args=() kwargs={'msg_src': 'SESWorker', 'request_id': 1604056247.0666442, 'result': ProcedureSummary(id=1, script_uri='file://scripts/eventbus.py', script_args={'init': <ProcedureInput(, subarray_id=1)>, 'run': <ProcedureInput(, )>}, history=<ProcessHistory(process_states=[(ProcedureState.CREATED, 1604056247.713874)], stacktrace=None)>, state=<ProcedureState.CREATED: 1>)}



Example session in a SKAMPI environment
---------------------------------------

From a shell, you can use the 'oet' command to trigger remote execution of a
full observation, e.g.,::

  # create process for telescope start-up and execute it
  oet create file:///scripts/startup.py
  oet start

  # create process for resource allocation script
  oet create file:///scripts/allocate_from_file_sb.py --subarray_id=3
  oet start scripts/example_sb.json

  # create process for configure/scan script
  oet create file:///scripts/observe_sb.py --subarray_id=3
  # run the script, specifying scheduling block JSON which defines
  # the configurations, and the order and number of scans
  oet start scripts/example_sb.json

  # create process for resource deallocation script
  oet create file:///scripts/deallocate.py --subarray_id=3
  # run with no arguments, which requests deallocation of all resources
  oet start

  # create process for telescope standby script
  oet create file:///scripts/standby.py
  oet start

