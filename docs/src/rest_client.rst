.. _rest-client:

***********
REST Client
***********

SKA observations will be controlled by ‘Procedures’. Each 'Procedure' comprises a 
Python script and a set of arguments, some of which will be set when the script 
is loaded and some at run-time. 

The management of 'Procedures' and the processes which execute them is handled by the 
:doc:`rest_server`, which implements the methods described in the :doc:`rest_api`.
This server lets the user:

* Load a requested Procedure script(s) with initialization arguments and 
  have it ready for execution.
* When required, pass run-time arguments to the script and start a process 
  executing it.

Aborting script execution is not required in this PI.

The REST Client provides a command line interface (CLI) through which
the user can communicate with the :doc:`rest_server` remotely. The
methods available through the REST Client map closely to the 
:doc:`rest_api` of the server and are described below:

+--------------------+---------------+-----------------------+-------------------------------------+
| REST Client Method | Parameters    | Default               | Description                         |
+====================+===============+=======================+=====================================+
| createAndExecute   | server_url    | "/api/v1/procedures"  | **Prepare and run a new procedure** |
|                    +---------------+-----------------------+                                     |
|                    | script_uri    | None                  | Load the requested script,          |
|                    +---------------+-----------------------+ prepare it for execution            | 
|                    | init_args     | None                  | and start it executing              |
|                    +---------------+-----------------------+                                     |
|                    | run_args      | None                  |                                     |
|                    +---------------+-----------------------+                                     |
|                    | silent        | True                  |                                     |
+--------------------+---------------+-----------------------+-------------------------------------+
| createProcess      | server_url    | "/api/v1/procedures"  | **Prepare a new procedure**         |
|                    +---------------+-----------------------+                                     |
|                    | script_uri    | None                  | Loads the requested script and      |
|                    +---------------+-----------------------+ prepares it for execution           |
|                    | init_args     | None                  |                                     |
|                    +---------------+-----------------------+                                     |
|                    | silent        | True                  |                                     |
+--------------------+---------------+-----------------------+-------------------------------------+
| list               | server url    | "/api/v1/procedures"  | **List procedures**                 |
|                    +---------------+-----------------------+                                     |
|                    | number        | None                  | Return the collection of all        |
|                    +---------------+-----------------------+ prepared and running procedures,    |
|                    | silent        | True                  | or the one specified by 'number'    |
+--------------------+---------------+-----------------------+-------------------------------------+
| startExecution     | server_url    | "/api/v1/procedures"  | **Start a Procedure Executing**     |
|                    +---------------+-----------------------+                                     |
|                    | number        | None                  | This starts a process executing     |
|                    +---------------+-----------------------+ the specified procedure. If         |
|                    | run_args      | None                  | none is specified then start        |
|                    +---------------+-----------------------+ the last one loaded.                |
|                    | silent        | True                  |                                     |
+--------------------+---------------+-----------------------+-------------------------------------+

The method parameters are described below:

+-------------+------------+----------------------------------------------------------------------+
| Parameter   | Python Type| Description                                                          |
+=============+============+======================================================================+
| server_url  | str        | URI of the REST Server.                                              |
+-------------+------------+----------------------------------------------------------------------+
| script_uri  | str        | URI of the script to execute, e.g., file:///path/to/obsscript.py     |
+-------------+------------+----------------------------------------------------------------------+
| init_args   | str        | The string representation of a Python dict with the input arguments  |
|             |            | to the "init" method of the script. The dict has two keys; "args"    |
|             |            | and "kwargs", for positional arguments and keyword/value arguments   |
|             |            | respectively. For example, below represents a call to                | 
|             |            | init(1,2,3,subarray=1)::                                             |
|             |            |                                                                      |
|             |            |    {                                                                 |
|             |            |      "args": [                                                       |
|             |            |        1,                                                            |
|             |            |        2,                                                            |
|             |            |        3                                                             |
|             |            |      ],                                                              |
|             |            |      "kwargs": {                                                     |
|             |            |        "subarray": "1"                                               |
|             |            |      }                                                               |
|             |            |    }                                                                 |
|             |            |                                                                      |
|             |            | It is IMPORTANT to note that 'init_args' is a string representation  |
|             |            | of a dict and should be enclosed in single quotes ' on the command   |
|             |            | line. Strings within the dict should be enclosed in double quotes ". |
+-------------+------------+----------------------------------------------------------------------+
| run_args    | dict       | String representation of a dict of input arguments to the "run"      | 
|             |            | method of the script.                                                |
|             |            | As for "init_args", the dict has two keys("args" and "kwargs") for   |
|             |            | positional arguments and keyword/value arguments respectively.       | 
+-------------+------------+----------------------------------------------------------------------+
| number      | int        | The index of a particular procedure in the list maintained by the    |
|             |            | REST Server                                                          |
+-------------+------------+----------------------------------------------------------------------+
| silent      | bool       | False if want to verbose reports on the interaction between the      |
|             |            | REST client and REST server.                                         |
+-------------+------------+----------------------------------------------------------------------+

Examples
========

Creating a procedure
--------------------
The session below creates a new 'Procedure', which loads the script and calls
the script’s init() function but does not commence execution.::

  tangodev@buster:~/ska/observation-execution-tool/oet/procedure/application$ python restclient.py createProcess --script_uri="file:///path/to/observing_script.py" --init_args='{"kwargs": {"subarray": 1, "sb_uri": "file:///path/to/scheduling_block_123.json"}}' 

The created procedure is returned and displayed as a dict::

  {'procedure': {'script_args': {'init': {'args': [], 'kwargs': {'sb_uri': 'file:///path/to/scheduling_block_123.json', 'subarray': 1}}, 'run': {'args': [], 'kwargs': {}}}, 'script_uri': 'file:///path/to/observing_script.py', 'state': 'READY', 'uri': 'http://localhost:5000/api/v1.0/procedures/1'}}

which contains all the information that was input plus a 'uri' field with 
the address of the procedure, in this case 'http://localhost:5000/api/v1.0/procedures/1'
where the 1 on the end indicates this is the first procedure to be loaded by the 
server. This number can be used as a shortcut address to this procedure in 
other REST client methods.

The script is ready to execute but is not yet executing, as shown by its state
being 'READY'.
 
Listing all procedures
----------------------
The session below lists all procedures known to the server, both running and 
non-running. This example shows that two procedures have been created: procedure #1 
that will run resource_allocation.py, and procedure #2 that will run 
observing_script.py::

  tangodev@buster:~/ska/observation-execution-tool/oet/procedure/application$ python restclient.py list

TBD: The output from restclient needs to be tidied up before inclusion here.

Listing one procedure
---------------------
A specific procedure can be listed by specifying its 'number'. The command below
lists procedure #1::

  tangodev@buster:~/ska/observation-execution-tool/oet/procedure/application$ python restclient.py list --number=1

TBD: List of output.

Starting procedure execution
----------------------------
A procedure can be told to start executing by the command 'startExecution'.
The example below requests execution of procedure #2, with late binding kw
argument scan_duration=14::

  tangodev@buster:~/ska/observation-execution-tool/oet/procedure/application$ python restclient.py startExecution --number=2 --run_args='{"kwargs": {"scan_duration": 14.0}}'

Load procedure and start immediately
------------------------------------
The effects of 'createProcess' and 'startExecution' are combined in the
'createAndExecute' method.
The example below requests execution of procedure #2, with late binding kw
argument scan_duration=14, and will start it executing immediately::

  tangodev@buster:~/ska/observation-execution-tool/oet/procedure/application$ python restclient.py createAndExecute --number=2 --run_args='{"kwargs": {"scan_duration": 14.0}}'
