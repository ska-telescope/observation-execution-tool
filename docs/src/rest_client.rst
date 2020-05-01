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
of http://rest-oet-release-name:5000/api/v1.0/procedures. If running the OET
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
|                    +---------------+--------------------------------------------+ prepare it for execution            |
|                    | args          | None                                       |                                     |
|                    +---------------+--------------------------------------------+                                     |
|                    | kwargs        | None                                       |                                     |
+--------------------+---------------+--------------------------------------------+-------------------------------------+
| list               | server-url    | See note above                             | **List procedures**                 |
|                    +---------------+--------------------------------------------+-------------------------------------+
|                    | number        | None                                       | Return info on the collection of all|
|                    |               |                                            | loaded and running procedures, or   |
|                    |               |                                            | info on the one specified by number |
+--------------------+---------------+--------------------------------------------+-------------------------------------+
| start              | server-url    | See note above                             | **Start a Procedure Executing**     |
|                    +---------------+--------------------------------------------+                                     |
|                    | number        | None                                       | Start a process executing           |
|                    +---------------+--------------------------------------------+ the procedure specified by number   |
|                    | args          | None                                       | or, if none is specified start      |
|                    +---------------+--------------------------------------------+ the last one loaded.                |
|                    | kwargs        | None                                       |                                     |
|                    |               |                                            | Only one procedure can be executing |
|                    |               |                                            | at any time                         |
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

    ID  URI                                             Script          State
  ----  ----------------------------------------------  --------------  -------
     1  http://172.16.13.18:5000/api/v1.0/procedures/1  file://test.py  READY

Note the use of both positional and keyword/value arguments for the
procedure on the command line.
Now create a second procedure: ::

  $ oet create file://test2.py 'goodbye'

giving: ::

    ID  URI                                          Script          State
  ----  -------------------------------------------  --------------  -------
     2  http://localhost:5000/api/v1.0/procedures/2  file://test2.py  READY

We can check the state of the procedures currently loaded by: ::

  $ oet list

giving: ::

    ID  URI                                          Script           State
  ----  -------------------------------------------  ---------------  -------
     1  http://localhost:5000/api/v1.0/procedures/1  file://test.py   READY
     2  http://localhost:5000/api/v1.0/procedures/2  file://test2.py  READY

Alternatively, we could check the state of procedure 2 by typing: ::

  $ oet list 2

giving: ::

    ID  URI                                          Script           State
  ----  -------------------------------------------  ---------------  -------
     2  http://localhost:5000/api/v1.0/procedures/2  file://test2.py  READY

Now that we have our procedures loaded we can start one of them running.
At this point we supply the index number of the procedure to run, and
some runtime arguments to pass to it if required. ::

  $ oet start 2 'bob' --simulate=false
 
giving: ::

    ID  URI                                          Script           State
  ----  -------------------------------------------  ---------------  -------
     2  http://localhost:5000/api/v1.0/procedures/2  file://test2.py  RUNNING

A 'list' command will give the same information: ::

  $ oet list

gives: ::

    ID  URI                                          Script           State
  ----  -------------------------------------------  ---------------  -------
     1  http://localhost:5000/api/v1.0/procedures/1  file://test.py   READY
     2  http://localhost:5000/api/v1.0/procedures/2  file://test2.py  RUNNING


Example session in a SKAMPI environment
---------------------------------------

From a shell, you can use the 'oet' command to trigger remote execution of a
full observation, e.g.,::

  # create process for telescope start-up and execute it
  oet create file:///scripts/startup.py
  oet start

  # create process for resource allocation script
  oet create file:///scripts/allocate_from_file.py
  oet start scripts/example_allocate.json --subarray_id=1

  # create process for configure/scan script
  oet create file:///scripts/observe.py
  # run the script, specifying configuration JSON to applied followed by a
  # 10 second scan. Set process_json to False if JSON should be passed through
  # directly to TMC (possibly required for new SDP schema)
  oet start scripts/example_configure.json 10 --subarray_id=1 --repeat=1 --process_json=True

  # create process for resource deallocation script
  oet create file:///scripts/deallocate.py
  # run with no arguments, which requests deallocation of all resources
  oet start

  # create process for telescope standby script
  oet create file:///scripts/standby.py
  oet start

