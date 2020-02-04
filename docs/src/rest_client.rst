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
the user can communicate with the :doc:`rest_server` remotely. The
methods available through the REST Client map closely to the 
:doc:`rest_api` of the server and are described below:

+--------------------+---------------+--------------------------------------------+-------------------------------------+
| REST Client Method | Parameters    | Default                                    | Description                         |
+====================+===============+============================================+=====================================+
| create             | server-url    | http://localhost:5000/api/v1.0/procedures  | **Prepare a new procedure**         |
|                    +---------------+--------------------------------------------+                                     |
|                    | script-uri    | None                                       | Load the requested script and       |
|                    +---------------+--------------------------------------------+ prepare it for execution            |
|                    | args          | None                                       |                                     |
|                    +---------------+--------------------------------------------+                                     |
|                    | kwargs        | None                                       |                                     |
+--------------------+---------------+--------------------------------------------+-------------------------------------+
| list               | server-url    | http://localhost:5000/api/v1.0/procedures  | **List procedures**                 |
|                    +---------------+--------------------------------------------+-------------------------------------+
|                    | number        | None                                       | Return info on the collection of all|
|                    |               |                                            | loaded and running procedures, or   |
|                    |               |                                            | info on the one specified by number |
+--------------------+---------------+--------------------------------------------+-------------------------------------+
| start              | server-url    | http://localhost:5000/api/v1.0/procedures  | **Start a Procedure Executing**     |
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

  tangodev: oet

Detailed help information for specific commands is also available e.g.::

  tangodev: oet create --help

Examples
--------

This section runs through an example session in which we will
load two new 'Procedures' and then run one of them.
First we load the procedures: ::

  tangodev: oet create file://test.py 'hello' --verbose=true

which will generate the output: ::

    ID  URI                                             Script          State
  ----  ----------------------------------------------  --------------  -------
     1  http://172.16.13.18:5000/api/v1.0/procedures/1  file://test.py  READY

Note the use of both positional and keyword/value arguments for the
procedure on the command line.
Now create a second procedure: ::

  tangodev: oet create file://test2.py 'goodbye'

giving: ::

    ID  URI                                          Script          State
  ----  -------------------------------------------  --------------  -------
     2  http://localhost:5000/api/v1.0/procedures/2  file://test2.py  READY

We can check the state of the procedures currently loaded by: ::

  tangodev: oet list

giving: ::

    ID  URI                                          Script           State
  ----  -------------------------------------------  ---------------  -------
     1  http://localhost:5000/api/v1.0/procedures/1  file://test.py   READY
     2  http://localhost:5000/api/v1.0/procedures/2  file://test2.py  READY

Alternatively, we could check the state of procedure 2 by typing: ::

  tangodev: oet list 2

giving: ::

    ID  URI                                          Script           State
  ----  -------------------------------------------  ---------------  -------
     2  http://localhost:5000/api/v1.0/procedures/2  file://test2.py  READY

Now that we have our procedures loaded we can start one of them running.
At this point we supply the index number of the procedure to run, and
some runtime arguments to pass to it if required. ::

  tangodev: oet start 2 'bob' --simulate=false
 
giving: ::

    ID  URI                                          Script           State
  ----  -------------------------------------------  ---------------  -------
     2  http://localhost:5000/api/v1.0/procedures/2  file://test2.py  RUNNING

A 'list' command will give the same information: ::

  tangodev: oet list

gives: ::

    ID  URI                                          Script           State
  ----  -------------------------------------------  ---------------  -------
     1  http://localhost:5000/api/v1.0/procedures/1  file://test.py   READY
     2  http://localhost:5000/api/v1.0/procedures/2  file://test2.py  RUNNING
