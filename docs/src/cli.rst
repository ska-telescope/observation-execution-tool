.. _cli:

*********************
OET command line tool
*********************

The ``oet`` command can be used to control a remote OET deployment [#f2]_.
The ``oet`` command has two sub-commands, ``procedure`` and ``activity``.

``oet procedure`` commands are used to control individual observing scripts,
which includes loading and starting and stopping script execution.

``oet activity`` commands are used to execute more general activities on the
telescope, for example running the allocate activity on SB with ID xxx.

See `Procedure`_ and `Activity`_ sections for further details on commands available
for each of the approaches.

Installation
************

The OET command line tool is available as the ``oet`` command at the terminal.
The OET CLI is packaged separately so it can be installed without OET backend
dependencies, such as PyTango. It can be installed into a Python environment,
and configured to access a remote OET deployment as detailed below:

.. code-block:: console

   $ pip install --upgrade ska_oso_oet_client

By default, the OET image has the CLI installed, meaning the CLI is accessible
from inside the running OET pod.

Configuration
*************

The address of the remote OET backend can be specified at the command line
via the ``server-url`` argument, or set session-wide by setting the
``OET_REST_URI`` environment variable, e.g.,

.. code-block:: console

  # provide the server URL when running the command, e.g.
  $ oet --server-url=http://my-oet-deployment.com:5000/api/v1.0 list

  # alternatively, set the server URL for a session by defining an environment variable
  $ export OET_REST_URI=http://my-oet-deployment.com:5000/api/v1.0
  $ oet list
  $ oet describe
  $ oet create ...

By default, the client assumes it is operating within a SKAMPI environment
and attempts to connect to a REST server using the default REST service name
of http://ska-oso-oet-rest:5000/api/v1.0. If running the OET
client within a SKAMPI pod, the ``OET_REST_URI`` should automatically be set.


Commands
********



Procedure
*********

Using ``oet procedure``, a remote OET deployment can be instructed to:

#. load a Python script using ``oet procedure create``;
#. run a function contained in the Python script using ``oet procedure start``;
#. stop a running Python function using ``oet procedure stop``;
#. observe OET messages and script messages using ``oet procedure listen``.

In addition, the current and historic state of Python processes running on
the backend can be inspected with

#. ``oet list`` to list all scripts that are prepared to run or are currently
   running;
#. ``oet describe`` to inspect the current and historic state of a specific
   process.

General help and specific help is available at the command line by adding the
``--help`` argument. For example:

.. code-block:: console

  # get a general overview of the OET CLI
  $ oet --help

  # get specific help on the oet create command
  $ oet create -- --help

  # get specific help on the oet describe command
  $ oet describe -- --help


Commands
--------

The commands available via ``oet`` are described below.

+----------------+------------+---------------------------------------------------------+-------------------------------------+
| OET CLI action | Parameters | Default                                                 | Description                         |
+================+============+=========================================================+=====================================+
| create         | server-url | See note above                                          | **Prepare a new procedure**         |
|                +------------+---------------------------------------------------------+                                     |
|                | script-uri | None                                                    | Load the requested script and       |
|                +------------+---------------------------------------------------------+ prepare it for execution.           |
|                | args       | None                                                    |                                     |
|                +------------+---------------------------------------------------------+ Arguments provided here are passed  |
|                | kwargs     | --subarray_id=1                                         | to the script init function, if     |
|                |            | --git_repo=                                             | defined                             |
|                |            | "http://gitlab.com/ska-telescope/oso/ska-oso-scripting" |                                     |
|                |            | --git_branch="master"                                   | OET maintains record of 10 newest   |
|                |            | --git_commit=None                                       | scripts which means creating 11th   |
|                |            | --create_env=False                                      | script will remove the oldest       |
|                |            |                                                         | script from the record.             |
+----------------+------------+---------------------------------------------------------+-------------------------------------+
| list           | server-url | See note above                                          | **List procedures**                 |
|                +------------+---------------------------------------------------------+-------------------------------------+
|                | pid        | None                                                    | Return info on the collection of 10 |
|                |            |                                                         | newest procedures, or info on the   |
|                |            |                                                         | one specified by process ID (pid)   |
+----------------+------------+---------------------------------------------------------+-------------------------------------+
| start          | server-url | See note above                                          | **Start a Procedure Executing**     |
|                +------------+---------------------------------------------------------+                                     |
|                | pid        | None                                                    | Start a process executing           |
|                +------------+---------------------------------------------------------+ the procedure specified by process  |
|                | args       | None                                                    | ID (pid) or, if none is specified   |
|                +------------+---------------------------------------------------------+ start the last one loaded.          |
|                | kwargs     | None                                                    |                                     |
|                |            |                                                         | Only one procedure can be executing |
|                |            |                                                         | at any time                         |
+----------------+------------+---------------------------------------------------------+-------------------------------------+
| stop           | server-url | See note above                                          | **Stop Procedure Execution**        |
|                +------------+---------------------------------------------------------+                                     |
|                | pid        | None                                                    | Stop a running process executing    |
|                +------------+---------------------------------------------------------+ the procedure specified by process  |
|                | run_abort  | True                                                    | ID (pid) or, if none is specified,  |
|                |            |                                                         | stop the currently running process. |
|                |            |                                                         |                                     |
|                |            |                                                         | If run_abort flag is True, OET will |
|                |            |                                                         | send Abort command to the SubArray  |
|                |            |                                                         | as part of script termination.      |
+----------------+------------+---------------------------------------------------------+-------------------------------------+
| describe       | server-url | See note above                                          | **Investigate a procedure**         |
|                +------------+---------------------------------------------------------+                                     |
|                | pid        | None                                                    | Displays the call arguments, state  |
|                |            |                                                         | history and, if the procedure       |
|                |            |                                                         | failed, the stack trace of a        |
|                |            |                                                         | specified process ID (pid). If no   |
|                |            |                                                         | pid is specified describe the last  |
|                |            |                                                         | process created.                    |
+----------------+------------+---------------------------------------------------------+-------------------------------------+
| Listen         | server-url | http://ska-oso-oet-rest:5000/api/v1.0/stream            | **Get real times scripts events**   |
|                +------------+---------------------------------------------------------+                                     |
|                |            |                                                         | Get a real time delivery of events  |
|                |            |                                                         | published by oet scripts            |
|                |            |                                                         |                                     |
|                |            |                                                         |                                     |
|                |            |                                                         |                                     |
|                |            |                                                         |                                     |
+----------------+------------+---------------------------------------------------------+-------------------------------------+

In the table 'args' refers to parameters specified by position on the command line, 'kwargs' to
those specified by name e.g. --myparam=12.


Examples
--------

This section runs through an example session in which we will
load two new 'Procedures' [#f1]_ and then run one of them.
First we load the procedure, and see the backend report that
it is creating a process with ID=1 to run the script.

.. code-block:: console

  $ oet procedure create file://test.py 'hello' --verbose=true

    ID  Script           Creation time        State
  ----  ---------------  -------------------  -------
     1  file://test.py   2020-09-30 10:30:12  CREATING

Note the use of both positional and keyword/value arguments for the
procedure on the command line. Now create a second procedure:

.. code-block:: console

  $ oet procedure create file://test2.py 'goodbye'

   ID   Script           Creation time        State
  ----  ---------------  -------------------  -------
    2  file://test2.py  2020-09-30 10:35:12  CREATING

Now create a third procedure that will be pulled from git:

.. code-block:: console

  $ oet procedure create git://test3.py --git_repo="http://foo.git" --git_branch="test" --create_env=True

   ID   Script           Creation time        State
  ----  ---------------  -------------------  -------
    3  git://test3.py    2020-09-30 10:40:12  CREATING

We can check the state of the procedures currently loaded:

.. code-block:: console

  $ oet procedure list

   ID   Script           Creation time        State
  ----  ---------------  -------------------  -------
     1  file://test.py   2020-09-30 10:30:12  READY
     2  file://test2.py  2020-09-30 10:35:12  READY
     3  git://test3.py   2020-09-30 10:40:12  READY

Alternatively, we could check the state of procedure 2 alone:

.. code-block:: console

  $ oet procedure list --pid=2

   ID   Script           Creation time        State
  ----  ---------------  -------------------  -------
    2   file://test2.py  2020-09-30 10:35:12  READY

Now that we have our procedures loaded we can start one of them running.
At this point we supply the ID of the procedure to run, and
some runtime arguments to pass to it if required. The backend responds
with the new status of the procedure.

.. code-block:: console

  $ oet procedure start --pid=2 'bob' --simulate=false

    ID   Script           Creation time        State
  ----  ---------------  -------------------  -------
    2   file://test2.py  2020-09-30 10:35:12  RUNNING

An ``oet procedure list`` command also shows the updated status of procedure #2:

.. code-block:: console

  $ oet procedure list

    ID   Script           Creation time        State
  ----  ---------------  -------------------  -------
     1  file://test.py   2020-09-30 10:30:12  READY
     2  file://test2.py  2020-09-30 10:35:12  RUNNING
     3  git://test3.py   2020-09-30 10:40:12  READY

An ``oet procedure describe`` command will give further detail on a procedure, no
matter its state.

.. code-block:: console

 $ oet procedure describe --pid=2

    ID  Script           URI
  ----  ---------------  -----------------------------------------
     2  file://test2.py  http://0.0.0.0:5000/api/v1.0/procedures/2

  Time                        State
  --------------------------  -------
  2020-09-30 10:19:38.011584  CREATING
  2020-09-30 10:19:38.016266  IDLE
  2020-09-30 10:19:38.017883  LOADING
  2020-09-30 10:19:38.018880  IDLE
  2020-09-30 10:19:38.019006  RUNNING 1
  2020-09-30 10:19:38.019021  READY
  2020-09-30 10:35:12.605270  RUNNING 2

  Index     Method     Arguments    Keyword Arguments
  --------  ---------  -----------  -------------------
      1      init      ['goodbye']  {'subarray_id': 1}
      2      run       ['bob']      {'simulate': false}

Describing a script from git shows additional information on the repository:

.. code-block:: console

 $ oet procedure describe --pid=3

    ID  Script           URI
  ----  ---------------  -----------------------------------------
     3  git://test3.py    http://0.0.0.0:5000/api/v1.0/procedures/3

  Time                        State
  --------------------------  -------
  2020-09-30 10:40:12.435305  CREATING
  2020-09-30 10:40:12.435332  IDLE
  2020-09-30 10:40:12.435364  LOADING
  2020-09-30 10:40:12.435401  IDLE
  2020-09-30 10:40:12.435433  RUNNING 1
  2020-09-30 10:40:12.435642  READY

 Index       Method    Arguments    Keyword Arguments
 --------   --------   ----------  -------------------
   1          init      []           {'subarray_id': 1}
   2          run       []           {}

  Repository           Branch    Commit
  ---------------      -------   -------------------
  http://foo.git       test

If the procedure failed, then the stack trace will also be displayed.

A 'listen' command will give the real time delivery of oet events published by scripts:

.. code-block:: console

  $ oet listen

  event: request.procedure.list
  data: args=() kwargs={'msg_src': 'FlaskWorker', 'request_id': 1604056049.4846392, 'pids': None}

  event: procedure.pool.list
  data: args=() kwargs={'msg_src': 'SESWorker', 'request_id': 1604056049.4846392, 'result': []}

  event: request.procedure.create
  data: args=() kwargs={'msg_src': 'FlaskWorker', 'request_id': 1604056247.0666442, 'cmd': PrepareProcessCommand(script_uri='file://scripts/eventbus.py', init_args=<ProcedureInput(, subarray_id=1)>)}

  event: procedure.lifecycle.created
  data: args=() kwargs={'msg_src': 'SESWorker', 'request_id': 1604056247.0666442, 'result': ProcedureSummary(id=1, script_uri='file://scripts/eventbus.py', script_args={'init': <ProcedureInput(, subarray_id=1)>, 'run': <ProcedureInput(, )>}, history=<ProcessHistory(process_states=[(ProcedureState.READY, 1604056247.713874)], stacktrace=None)>, state=<ProcedureState.READY: 1>)}

Press :kbd:`Control-c` to exit from ``oet listen``.

Example session in a SKAMPI environment
---------------------------------------

From a shell, you can use the 'oet' command to trigger remote execution of a
full observation, e.g.,

.. code-block:: console

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


.. rubric:: Footnotes

.. [#f2] Specifically, the cli tool acts as a REST client that interfaces with
   the OET REST API described in :doc:`architecture_module_rest_api`.
.. [#f1] For reference, the OET architecture refers to Python scripts as `Procedures`.
