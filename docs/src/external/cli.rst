.. _cli:

*********************
OET command line tool
*********************

The ``oet`` command can be used to control a remote OET deployment [#f2]_.
The ``oet`` command has two sub-commands, ``procedure`` and ``activity``.

``oet procedure`` commands are used to control individual observing scripts,
which includes loading and starting and stopping script execution.

``oet activity`` commands are used to execute more general activities on the
telescope, for example running the observe activity on SB with ID xxx.

See `Procedure`_ and `Activity`_ sections for further details on commands available
for each of the approaches.

General help and specific help is available at the command line by adding the
``--help`` argument. For example:

.. code-block:: console

  # get a general overview of the OET CLI
  $ oet procedure --help
  $ oet activity --help

  # get specific help on the oet create command
  $ oet procedure create --help

  # get specific help on the oet describe command
  $ oet activity describe --help

Installation
============

The OET command line tool is available as the ``oet`` command at the terminal.
The OET CLI is packaged separately so it can be installed without OET backend
dependencies, such as PyTango. It can be installed into a Python environment,
and configured to access a remote OET deployment as detailed below:

.. code-block:: console

   $ pip install --upgrade ska_oso_oet_client -i https://artefact.skao.int/repository/pypi-all/simple

By default, the OET image has the CLI installed, meaning the CLI is accessible
from inside the running OET pod.

Configuration
=============

The address of the remote OET backend can be specified at the command line
via the ``server-url`` argument, or set session-wide by setting the
``OET_URL`` environment variable, e.g.,

.. code-block:: console

  # provide the server URL when running the command, e.g.
  $ oet --server-url=http://my-oet-deployment.com:5000/ska-oso-oet/oet/api/v1 procedure list

  # alternatively, set the server URL for a session by defining an environment variable
  $ export OET_URL=http://my-oet-deployment.com:5000/ska-oso-oet/oet/api/v1
  $ oet procedure list
  $ oet activity describe
  $ oet procedure create ...

By default, the client assumes it is operating within a Kubernetes environment
and attempts to connect to a REST server using the default REST service name
of http://ska-oso-oet-rest:5000/ska-oso-oet/oet/api/v1.


Commands
========


Common
------

The ``oet`` CLI tool has ``listen`` command which is neither activity or procedure specific.
It is used to observe OET messages and script messages from, procedure, activity and several
other topics.

+----------------+------------+---------------------------------------------------------+-------------------------------------+
| OET CLI action | Parameters | Default                                                 | Description                         |
+================+============+=========================================================+=====================================+
| Listen         | server-url | See `Configuration`_ section                            | **Get real times scripts events**   |
|                +------------+---------------------------------------------------------+                                     |
|                |            |                                                         | Get a real time delivery of events  |
|                |            |                                                         | published by oet server/scripts     |
+----------------+------------+---------------------------------------------------------+-------------------------------------+


Examples
~~~~~~~~

A 'listen' command will give the real time delivery of oet events published by scripts:

.. code-block:: console

  $ oet listen

  event: request.procedure.list
  data: args=() kwargs={'msg_src': 'FlaskWorker', 'request_id': 1604056049.4846392, 'pids': None}

  event: procedure.pool.list
  data: args=() kwargs={'msg_src': 'SESWorker', 'request_id': 1604056049.4846392, 'result': []}

  event: activity.pool.list
  data: args=() kwargs={'msg_src': 'ActivityWorker', 'request_id': 1604056078.4847652, 'result': []}

  event: request.procedure.create
  data: args=() kwargs={'msg_src': 'FlaskWorker', 'request_id': 1604056247.0666442, 'cmd': PrepareProcessCommand(script_uri='file://scripts/eventbus.py', init_args=<ProcedureInput(, subarray_id=1)>)}

  event: procedure.lifecycle.created
  data: args=() kwargs={'msg_src': 'SESWorker', 'request_id': 1604056247.0666442, 'result': ProcedureSummary(id=1, script_uri='file://scripts/eventbus.py', script_args={'init': <ProcedureInput(, subarray_id=1)>, 'run': <ProcedureInput(, )>}, history=<ProcessHistory(process_states=[(ProcedureState.READY, 1604056247.713874)], stacktrace=None)>, state=<ProcedureState.READY: 1>)}

Press :kbd:`Control-c` to exit from ``oet listen``.


Procedure
---------

Using ``oet procedure``, a remote OET deployment can be instructed to:

#. load a Python script using ``oet procedure create``;
#. run a function contained in the Python script using ``oet procedure start``;
#. stop a running Python function using ``oet procedure stop``;

In addition, the current and historic state of Python processes running on
the backend can be inspected with

#. ``oet procedure list`` to list all scripts that are prepared to run or are
   currently running;
#. ``oet procedure describe`` to inspect the current and historic state of a
   specific process.

The commands available via ``oet procedure`` are described below.

+----------------+------------+---------------------------------------------------------+-------------------------------------+
| OET CLI action | Parameters | Default                                                 | Description                         |
+================+============+=========================================================+=====================================+
| create         | server-url | See `Configuration`_ section                            | **Prepare a new procedure**         |
|                +------------+---------------------------------------------------------+                                     |
|                | script-uri | None                                                    | Load the requested script and       |
|                +------------+---------------------------------------------------------+ prepare it for execution.           |
|                | args       | None                                                    |                                     |
|                +------------+---------------------------------------------------------+ Arguments provided here are passed  |
|                | kwargs     | \-\-subarray_id=1                                       | to the script init function, if     |
|                |            | \-\-git_repo=                                           | defined                             |
|                |            | "http://gitlab.com/ska-telescope/oso/ska-oso-scripting" |                                     |
|                |            | \-\-git_branch="master"                                 | OET maintains record of 10 newest   |
|                |            | \-\-git_commit=None                                     | scripts which means creating 11th   |
|                |            | \-\-create_env=False                                    | script will remove the oldest       |
|                |            |                                                         | script from the record.             |
+----------------+------------+---------------------------------------------------------+-------------------------------------+
| list           | server-url | See `Configuration`_ section                            | **List procedures**                 |
|                +------------+---------------------------------------------------------+                                     |
|                | pid        | None                                                    | Return info on the collection of 10 |
|                |            |                                                         | newest procedures, or info on the   |
|                |            |                                                         | one specified by process ID (pid)   |
+----------------+------------+---------------------------------------------------------+-------------------------------------+
| start          | server-url | See `Configuration`_ section                            | **Start a Procedure Executing**     |
|                +------------+---------------------------------------------------------+                                     |
|                | pid        | None                                                    | Start a process executing           |
|                +------------+---------------------------------------------------------+ the procedure specified by process  |
|                | args       | None                                                    | ID (pid) or, if none is specified   |
|                +------------+---------------------------------------------------------+ start the last one loaded.          |
|                | kwargs     | None                                                    |                                     |
|                |            |                                                         | Only one procedure can be executing |
|                |            |                                                         | at any time.                        |
|                +------------+---------------------------------------------------------+                                     |
|                | listen     | True                                                    | listen flag is set to True by       |
|                |            |                                                         | default which means that events are |
|                |            |                                                         | shown on the command line unless    |
|                |            |                                                         | is is explicitly set to False.      |
+----------------+------------+---------------------------------------------------------+-------------------------------------+
| stop           | server-url | See `Configuration`_ section                            | **Stop Procedure Execution**        |
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
| describe       | server-url | See `Configuration`_ section                            | **Investigate a procedure**         |
|                +------------+---------------------------------------------------------+                                     |
|                | pid        | None                                                    | Displays the call arguments, state  |
|                |            |                                                         | history and, if the procedure       |
|                |            |                                                         | failed, the stack trace of a        |
|                |            |                                                         | specified process ID (pid). If no   |
|                |            |                                                         | pid is specified describe the last  |
|                |            |                                                         | process created.                    |
+----------------+------------+---------------------------------------------------------+-------------------------------------+

In the table 'args' refers to parameters specified by position on the command line, 'kwargs' to
those specified by name e.g. --myparam=12.


Examples
~~~~~~~~

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
     2  file://test2.py  http://0.0.0.0:5000/ska-oso-oet/oet/api/v1/procedures/2

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
     3  git://test3.py    http://0.0.0.0:5000/ska-oso-oet/oet/api/v1/procedures/3

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


Example session in a deployed environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you are working with a complete system such that the OET is able to communicate
with TMC and the various devices are deployed (Dish, MCCS, CSP, SDP, etc.) the OET
can be used from a shell to trigger remote execution of a full observation, e.g.

.. code-block:: console

  # create process for running observation, including allocation and configuration/scan
  oet procedure create file:///scripts/allocate_and_observe_sb.py --subarray_id=3
  # run the script, specifying scheduling block JSON which defines
  # the configurations, and the order and number of scans
  oet procedure start scripts/example_sb.json


Activity
--------

Using ``oet activity``, a remote OET deployment can be instructed to:

#. execute a observing activity of a Scheduling Block with ``oet activity run``

In addition, the current and historic state of Activities can be inspected with

#. ``oet activity list`` to list all activities that have been started;
#. ``oet activity describe`` to inspect the current and historic state of a
   specific activity.

The commands available via ``oet activity`` are described below.

+----------------+---------------+---------------------------------------------------------+-------------------------------------+
| OET CLI action | Parameters    | Default                                                 | Description                         |
+================+===============+=========================================================+=====================================+
| run            | server-url    | See `Configuration`_ section                            | **Run an activity of an SB**        |
|                +---------------+---------------------------------------------------------+                                     |
|                | activity-name | None                                                    | Create and run a script referenced  |
|                +---------------+---------------------------------------------------------+ by an activity defined in an SB.    |
|                | sbd-id        | None                                                    | The activity-name and sbd-id are    |
|                +---------------+---------------------------------------------------------+ mandatory arguments. script-args is |
|                | script-args   | None                                                    | a dictionary defining function name |
|                +---------------+---------------------------------------------------------+ as a key (e.g. 'init') and any      |
|                | prepare-only  | False                                                   | keyword arguments to be passed for  |
|                +---------------+---------------------------------------------------------+ the function on top of arguments    |
|                | create-env    | False                                                   | present in the SB. Only keyword args|
|                +---------------+---------------------------------------------------------+ are currently allowed.              |
|                | listen        | True                                                    |                                     |
|                |               |                                                         | preparep-only should be set to False|
|                |               |                                                         | if the script referred to by SB and |
|                |               |                                                         | activity is not to be run yet. To   |
|                |               |                                                         | start a prepared script, use the    |
|                |               |                                                         | `oet procedure` commands.           |
|                |               |                                                         |                                     |
|                |               |                                                         | create-env flag should be set to    |
|                |               |                                                         | True if script referred to by SB is |
|                |               |                                                         | a Git script and requires a non-    |
|                |               |                                                         | default environment to run.         |
+----------------+---------------+---------------------------------------------------------+-------------------------------------+
| list           | server-url    | See `Configuration`_ section                            | **List activities**                 |
|                +---------------+---------------------------------------------------------+                                     |
|                | aid           | None                                                    | Return info on the collection of 10 |
|                |               |                                                         | newest activities, or info on the   |
|                |               |                                                         | one specified by activity ID (aid)  |
+----------------+---------------+---------------------------------------------------------+-------------------------------------+
| describe       | server-url    | See note above                                          | **Investigate an activity**         |
|                +---------------+---------------------------------------------------------+                                     |
|                | aid           | None                                                    | Displays the script arguments, and  |
|                |               |                                                         | the state history of a specified    |
|                |               |                                                         | activity ID (aid). If no aid is     |
|                |               |                                                         | specified describe the last activity|
|                |               |                                                         | created.                            |
+----------------+---------------+---------------------------------------------------------+-------------------------------------+

The activity name is given in the SBD and although this can be set to anything in the PDM,
a typical observation was envisaged as having multiple activities, including ``allocate``
(assign resources) and ``observe`` (configure and then run a scan). It is now assumed that only
one script will be used and OSO Scripting, for example, now only contains a single script,
``allocate_and_observe.py``. This could be given any activity name, with ``observe`` probably
being the best choice.

One reason for only wanting to run one activity per SBD is that currently each would create
a separate Scheduling Block Instance (SBI) as the OET has no state management that allows it to
link different activities taking place as part of the same SBD. This might change in the future.

Examples
~~~~~~~~

This section runs through an example session in which we will
run an activity with arguments to the script. We will also demonstrate
the more advanced use of controlling activity execution with additional
``oet procedure`` commands. For this we will prepare an activity without
executing it and use the ``oet procedure`` commands to run the prepared
activity.

.. code-block:: console

  $ oet activity run observe sbd-123 --script-args='{"init": {"kwargs": {"foo": "bar"}}}'

    ID  Activity    SB ID    Creation Time          Procedure ID  State
  ----  ----------  -------  -------------------  --------------  ---------
     1  observe     sbd-123  2023-01-06 13:56:47               1  REQUESTED

Note the use of keyword arguments for the script arguments. These will be
passed as arguments when each function in the script is run. If the given
keyword argument is already defined in the Scheduling Block, the value
will be overwritten with the user provided one.

The activity has now been started and will complete without any further
interaction from the user.

For an example of more advanced use of the activity interface, run an activity
but set the ``prepare-only`` flag to True:

.. code-block:: console

  $ oet activity run observe sbd-123 --prepare-only=True

    ID  Activity    SB ID    Creation Time          Procedure ID  State
  ----  ----------  -------  -------------------  --------------  ---------
     2  observe     sbd-123  2023-01-06 13:56:56               2  REQUESTED

We can check the state of the activities currently present:

.. code-block:: console

  $ oet activity list

    ID  Activity    SB ID    Creation Time          Procedure ID  State
  ----  ----------  -------  -------------------  --------------  ---------
     1  observe     sbd-123  2023-01-06 13:56:47               1  COMPLETE
     2  observe     sbd-123  2023-01-06 13:56:56               2  PREPARED


Note that the first activity prepares and runs the script automatically but
the second one only prepares the script but does not run it. To run the script
of the second activity we need to note the ``Procedure ID`` for the activity
and use ``oet procedure`` commands to run the script:

.. code-block:: console

  $ oet procedure start --pid=2

    ID   Script             Creation time        State
  ----  ---------------    -------------------  -------
    2   file://observe.py  2023-01-06 13:57:25  RUNNING

An ``oet activity describe`` command will give further detail on an activity.

.. code-block:: console

 $ oet activity describe --aid=1

    ID  Activity    SB ID      Procedure ID  State
  ----  ----------  -------  --------------  ---------
     1  observe     sbd-123               1  COMPLETE

  URI                                        Prepare Only
  -----------------------------------------  --------------
  http://0.0.0.0:5000/ska-oso-oet/oet/api/v1/activities/1  False

  Time                        State
  --------------------------  ---------
  2023-01-06 13:56:47.655175  REQUESTED
  2023-01-06 13:56:47.934723  PREPARED
  2023-01-06 13:56:48.004753  RUNNING
  2023-01-06 13:56:50.382756  COMPLETE


  Script Arguments
  ----------------

  Method    Arguments    Keyword Arguments
  --------  -----------  -------------------
  init      [1, 'foo']   {'foo': 'bar'}


You can also view the details of the script that was run by the activity:

.. code-block:: console

 $ oet procedure describe --pid=1

    ID  Script                URI
  ----  ---------------       -----------------------------------------
     1  file://observe.py    http://0.0.0.0:5000/ska-oso-oet/oet/api/v1/procedures/1

  Time                        State
  --------------------------  -------
  2023-01-06 13:56:47.655175  CREATING
  2023-01-06 13:56:47.663742  IDLE
  2023-01-06 13:56:47.665741  LOADING
  2023-01-06 13:56:47.730696  IDLE
  2023-01-06 13:56:47.731965  RUNNING 1
  2023-01-06 13:56:47.934723  READY
  2023-01-06 13:56:48.004753  RUNNING 2
  2023-01-06 13:56:50.382756  READY

 Index       Method    Arguments     Keyword Arguments
 --------   --------   ----------   -------------------
   1          init      [1, 'foo']    {'foo': 'bar'}
   2          run       []            {}



.. rubric:: Footnotes

.. [#f2] Specifically, the cli tool acts as a REST client that interfaces with
   the OET REST API described in :doc:`../internal/architecture/architecture_module_rest_api`.
.. [#f1] For reference, the OET architecture refers to Python scripts as `Procedures`.
