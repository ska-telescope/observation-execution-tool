.. _architecture_module_rest_api:

*********************
Module View: REST API
*********************

1. Interface Identity
=====================
OET REST API presents REST resources that can be used to manage the lifecycle of Python scripts running on a remote
server and to inspect their status.

2. Resources
============
A ‘Procedure’ represents a Python script to run, or that is running, on the backend. The REST API operates on
Procedures.

The standard workflow is to use the API to:

1. Instruct the backend to prepare a script for execution by using HTTP POST to upload a JSON ``Procedure`` to
   <namespace, default ska-oso-oet>/api/v<OET major version>/procedures
2. Start script execution by uploading an updated JSON ``Procedure`` with a ``ProcedureState`` of ``RUNNING``.
3. (optional) a running script can be terminated by using PUT to upload a JSON ``Procedure`` with a ``ProcedureState``
   of ``STOPPED``.

The current status of a script execution can be inspected at any time by reading the JSON ``Procedure`` with HTTP GET.

This workflow has been mapped to the following REST resources:

.. list-table:: Procedure REST resources
   :widths: 5 15 80
   :header-rows: 1

   * - HTTP Method
     - Resource URL
     - Description
   * - GET
     - ``/api/v1/procedures``
     - **List procedures**
       |br|
       |br|
       Return the collection of all prepared and running procedures.
   * - GET
     - ``/api/v1/procedures/<id>``
     - Return a procedure definition
   * - GET
     - ``/api/v1/stream``
     - **Streaming realtime OET events**
       |br|
       |br|
       Return an SSE data stream of OET events as they are published by the OET and scripts.
   * - POST
     - ``/api/v1/procedures``
     - **Prepare a new procedure**
       |br|
       |br|
       Loads the requested script and prepares it for execution.
   * - PUT
     - ``/api/v1/procedures/<id>``
     - **Modify the state of a prepared procedure**
       |br|
       |br|
       This can be used to start execution by setting the Procedure ``state`` attribute to ``RUNNING`` or stop execution
       by setting ``state`` to ``STOPPED``.

An ‘Activity’ represents an action which a user will command the telescope to perform, eg 'allocate'

.. list-table:: Activity REST resources
   :widths: 5 15 80
   :header-rows: 1

   * - HTTP Method
     - Resource URL
     - Description
   * - GET
     - ``/api/v1/activities``
     - **List activities**
       |br|
       |br|
       Return the collection of all activities.
   * - GET
     - ``/api/v1/activities/<activity_id>``
     - **Get activity**
       |br|
       |br|
       Return the a summary of the activity with given id.
   * - POST
     - ``/api/v1/activities``
     - **Prepare a new activity**
       |br|
       |br|
       Loads the script from the SBDefinition for the given activity and prepares it for execution. Response is an ActivitySummary


3. Data Types and Constants
===========================

Type: ``Procedure``
-------------------
``Procedure`` is used to represent a Python script running in a Python process on the OET backend. Attributes are:

  * ``string uri``: read-only URI of this procedure. Defined by the server on procedure creation.
  * ``FileSystemScript/GitScript script``: Script details containing script_uri, e.g., ``file:///path/to/obsscript.py``, and additional information like git arguments.
  * ``CallArgs script_args``: arguments provided to the script at initialisation time and main execution time.
  * ``ProcedureState state``: current state of this ``Procedure``.
  * ``ProcedureHistory history``: timestamped execution history for this ``Procedure``.

Example
```````
Below is an example ``Procedure`` JSON object. This resource
(located at URI http://localhost:5000/ska-oso-oet/oet/api/v1/procedures/1), represents a
script (located on disk at /path/to/observing_script.py), that has been loaded
and its initialisation method called with two arguments (e.g, the script init
function was called as
``init(subarray_id=1, sb_uri=’file:///path/to/scheduling_block_123.json’)``. The
script is ready to execute but is not yet executing, as shown by its state
being ``READY``::

    {
        "script_args": {
          "init": {
            "args": [],
            "kwargs": {
              "sb_uri": "file:///path/to/scheduling_block_123.json",
              "subarray_id": 1
            }
          },
          "run": {
            "args": [],
            "kwargs": {}
          }
        },
        "script": {
            "script_type": "filesystem",
            "script_uri": "file:///path/to/observing_script.py",
        },
        "history": {
            "process_states": [
               ("CREATING", 1601463545.57689632),
               ("IDLE", 1601463545.57843814),
               ("LOADING", 1601463545.58043561),
               ("IDLE", 1601463545.58865546),
               ("RUNNING", 1601463545.62904726),
               ("READY", 1601463545.7789776)
            ],
            "stacktrace": null
        },
        "state": "READY",
        "uri": "http://localhost:5000/ska-oso-oet/oet/api/v1/procedures/1"
    }


If user wanted to run script located in a git repository ``http://gitrepo.git`` in branch ``test``, the script JSON would look as below::

    { ...
        "script": {
            "script_type": "git",
            "script_uri": "git:///path/to/observing_script.py",
            "git_args": {"git_repo": "http://gitrepo.git", "git_branch": "test"}
        } ...
    }

Type: ``FileSystemScript``
--------------------------
``FileSystemScript`` represents the script to be run from the file system. It has ``script_uri`` argument which
points to an observing script present on the file system and ``script_type`` which has the value of ``filesystem``.

Type: ``GitScript``
-------------------
``GitScript`` inherits from ``FileSystemScript``, which means it also has a ``script_uri`` argument and
``script_type`` of ``git``. Additionally it has an argument, ``GitArgs`` which points to the git repository
the given script is located in. The arguments for ``GitArgs`` are:

    * ``git_repo`` which points to the full URL of the repository
    * ``git_branch`` if specifying other than the default ``master`` branch
    * ``git_commit`` if wanting to point to a specific commit within the repository.

Type: ``CallArgs``
------------------
``CallArgs`` represents the arguments to be passed to functions in the user script when those functions are called.
Attributes are:

  * ``FunctionArgs init``: arguments passed to the script ``init`` function at script creation and initialisation time.
  * ``FunctionArgs run``: arguments passed to the script ``main`` function when the main execution function is called.

Type: ``FunctionArgs``
----------------------
``FunctionArgs`` captures the positional arguments and keywords arguments (to be) passed to a Python
function. Attribute are:

  * ``list args``: list of positional arguments for the Python function, e.g., ``"args": [1, 2, 3]``
  * ``dict kwargs``: dictionary of keywords arguments, e.g., ``"kwargs": {"subarray_id": 1}``

Type: ``ProcedureState``
------------------------
``ProcedureState`` is an enumeration representing the current lifecycle state of the Python process running the user
script. It can be one of:

  * ``IDLE``: state between script preparation steps where no action is ongoing.
  * ``CREATING``: script creation has been started.
  * ``LOADING``: loading the specified script file to be executed.
  * ``READY``: script is ready to run specified function, e.g. ``init`` or ``main``.
  * ``RUNNING``: script is running, i.e., the script's ``init`` or ``main`` function is currently executing.
  * ``STOPPED``: script was terminated by the OET before the script could complete.
  * ``COMPLETE``: the script completed successfully, i.e., the ``main`` function completed and no exception was raised.
  * ``FAILED``: an exception was raised during script preparation or execution.

Type: ``ProcedureHistory``
--------------------------
``ProcedureHistory`` represents a timeline of ``ProcedureStates`` that the ``Procedure`` has passed through. Attributes
are:

  * ``list process_states``: a List of ``ProcedureStates`` and timestamps when that ``ProcedureState`` was
    reached, e.g. ``process_states: [('CREATING', 18392174.543), ('RUNNING', 18392143.546), ('COMPLETE', 183925456.744)]``.
  * ``string stacktrace``: populated with the stacktrace from the script if the final ``ProcedureState`` is ``FAILED``.
    This attribute is set to None for any other final state.


4. Error Handling
=================

Accessing the URL of a ``Procedure`` that does not exist on the backend or whose history has expired will result in a
HTTP 404 error::

    tangodev@buster:~/ska/ska-oso-oet$ curl -i http://localhost:5000/ska-oso-oet/oet/api/v1/procedures/4
    HTTP/1.0 404 NOT FOUND
    Content-Type: application/json
    Content-Length: 103
    Server: Werkzeug/1.0.1 Python/3.7.3
    Date: Thu, 18 Feb 2021 17:40:30 GMT

    {"error": "404 Not Found", "type": "ResourceNotFound", "Message": "No information available for PID=4"}


5. Variability
==============
None

6. Quality Attribute Characteristics
====================================
None

7. Rationale and Design Issues
==============================
The procedure history is limited, and at some point a Procedure REST resource will become unavailable as it becomes
superseded by new Procedures and that history slot is reclaimed. This is not expected to be a problem as a maximum of
one script can run at any one time, so even a small history allows a reasonable amount of time for that Procedure
history to be inspected.

8. Usage Guide
==============
The following examples show some interactions with the REST service from the
command line, using curl to send input to the service and with responses
output to the terminal.

Creating a procedure
--------------------
The session below creates a new procedure, which loads the script and calls
the script’s init() function, but does not commence execution. The created
procedure is returned as JSON. Note that in the return JSON the procedure URI
is defined. This URI can be used in a PUT request that commences script
execution::

    tangodev@buster:~/ska/ska-oso-oet$ curl -i -H "Content-Type: application/json" -X POST -d '{"script_uri":"file:///path/to/observing_script.py", "script_args": {"init": { "kwargs": {"subarray_id": 1, "sb_uri": "file:///path/to/scheduling_block_123.json"} } }}' http://localhost:5000/ska-oso-oet/oet/api/v1/procedures
    HTTP/1.0 201 CREATED
    Content-Type: application/json
    Content-Length: 424
    Server: Werkzeug/0.16.0 Python/3.7.3
    Date: Wed, 15 Jan 2020 10:08:01 GMT

    {
      "procedure": {
        "script_args": {
          "init": {
            "args": [],
            "kwargs": {
              "sb_uri": "file:///path/to/scheduling_block_123.json",
              "subarray_id": 1
            }
          },
          "run": {
            "args": [],
            "kwargs": {}
          }
        },
        "script": {
            "script_type": "filesystem",
            "script_uri": "file:///path/to/observing_script.py"
        },
        "history": {
            "process_states": [
               ("CREATING", 1601463545.7589678),
               ("IDLE", 1601463545.7598525),
               ("LOADING", 1601463545.7649524),
               ("IDLE", 1601463545.7668241),
               ("RUNNING", 1601463545.7694371),
               ("READY", 1601463545.7748005)
            ],
            "stacktrace": null
        },
        "state": "READY",
        "uri": "http://localhost:5000/ska-oso-oet/oet/api/v1/procedures/2"
      }
    }

Listing all procedures
----------------------
The session below lists all procedures, both running and non-running. This
example shows two procedures have been created: procedure #1 that will run
resource_allocation.py, and procedure #2 that will run observing_script.py::

    tangodev@buster:~/ska/ska-oso-oet$ curl -i http://localhost:5000/ska-oso-oet/oet/api/v1/procedures
    HTTP/1.0 200 OK
    Content-Type: application/json
    Content-Length: 913
    Server: Werkzeug/0.16.0 Python/3.7.3
    Date: Wed, 15 Jan 2020 10:11:42 GMT

    {
      "procedures": [
        {
          "script_args": {
            "init": {
              "args": [],
              "kwargs": {
                "dishes": [
                  1,
                  2,
                  3
                ]
              }
            },
            "run": {
              "args": [],
              "kwargs": {}
            }
          },
          "script": {
            "script_type": "filesystem",
            "script_uri": "file:///path/to/resource_allocation.py"
          },
          "history": {
              "process_states": [
                   ("CREATING", 1601463545.7589678),
                   ("IDLE", 1601463545.7598525),
                   ("LOADING", 1601463545.7649524),
                   ("IDLE", 1601463545.7668241),
                   ("RUNNING", 1601463545.7694371),
                   ("READY", 1601463545.7748005)
                ],
              "stacktrace": null
		  },
          "state": "READY",
          "uri": "http://localhost:5000/ska-oso-oet/oet/api/v1/procedures/1"
        },
        {
          "script_args": {
            "init": {
              "args": [],
              "kwargs": {
                "sb_uri": "file:///path/to/scheduling_block_123.json",
                "subarray_id": 1
              }
            },
            "run": {
              "args": [],
              "kwargs": {}
            }
          },
          "script": {
            "script_type": "filesystem",
            "script_uri": "file:///path/to/observing_script.py"
          },
          "history": {
               "process_states": [
                   ("CREATING", 1601463545.7589678),
                   ("IDLE", 1601463545.7598525),
                   ("LOADING", 1601463545.7649524),
                   ("IDLE", 1601463545.7668241),
                   ("RUNNING", 1601463545.7694371),
                   ("READY", 1601463545.7748005)
               ],
               "stacktrace": null
          },
          "state": "READY",
          "uri": "http://localhost:5000/ska-oso-oet/oet/api/v1/procedures/2"
        }
      ]
    }

Listing one procedure
---------------------
A specific procedure can be listed by a GET request to its specific URI. The
session below lists procedure #1::

    tangodev@buster:~/ska/ska-oso-oet$ curl -i http://localhost:5000/ska-oso-oet/oet/api/v1/procedures/1
    HTTP/1.0 200 OK
    Content-Type: application/json
    Content-Length: 417
    Server: Werkzeug/0.16.0 Python/3.7.3
    Date: Wed, 15 Jan 2020 10:18:26 GMT

    {
      "procedure": {
        "script_args": {
          "init": {
            "args": [],
            "kwargs": {
              "dishes": [
                1,
                2,
                3
              ]
            }
          },
          "run": {
            "args": [],
            "kwargs": {}
          }
        },
        "script": {
          "script_type": "filesystem",
          "script_uri": "file:///path/to/resource_allocation.py"
        },
        "history": {
            "process_states": [
               ("CREATING", 1601463545.7589678),
               ("IDLE", 1601463545.7598525),
               ("LOADING", 1601463545.7649524),
               ("IDLE", 1601463545.7668241),
               ("RUNNING", 1601463545.7694371),
               ("READY", 1601463545.7748005)
            ],
            "stacktrace": null
        },
        "state": "READY",
        "uri": "http://localhost:5000/ska-oso-oet/oet/api/v1/procedures/1"
      }
    }

Starting procedure execution
----------------------------
The signal to begin script execution is to change the state of a procedure to
``RUNNING``. This is achieved with a PUT request to the resource. Any
additional late-binding arguments to pass to the script’s run() function
should be defined in the ‘run’ script_args key.

The example below requests execution of procedure #2, with late binding kw
argument scan_duration=14::

    tangodev@buster:~/ska/ska-oso-oet$ curl -i -H "Content-Type: application/json" -X PUT -d '{"script_args": {"run": {"kwargs": {"scan_duration": 14.0}}}, "state": "RUNNING"}' http://localhost:5000/ska-oso-oet/oet/api/v1/procedures/2
    HTTP/1.0 200 OK
    Content-Type: application/json
    Content-Length: 467
    Server: Werkzeug/0.16.0 Python/3.7.3
    Date: Wed, 15 Jan 2020 10:14:06 GMT

    {
      "procedure": {
        "script_args": {
          "init": {
            "args": [],
            "kwargs": {
              "sb_uri": "file:///path/to/scheduling_block_123.json",
              "subarray_id": 1
            }
          },
          "run": {
            "args": [],
            "kwargs": {
              "scan_duration": 14.0
            }
          }
        },
        "script": {
          "script_type": "filesystem",
          "script_uri": "file:///path/to/observing_script.py"
        },
        "history": {
            "process_states": [
               ("CREATING", 1601463545.7589678),
               ("IDLE", 1601463545.7598525),
               ("LOADING", 1601463545.7649524),
               ("IDLE", 1601463545.7668241),
               ("RUNNING", 1601463545.7694371),
               ("READY", 1601463545.7748005)
             ],
            "stacktrace": null
        }
        "state": "READY",
        "uri": "http://localhost:5000/ska-oso-oet/oet/api/v1/procedures/2"
      }
    }


Terminate process execution
---------------------------
The signal to abort script mid-execution is to change the state of a procedure to
``STOPPED``. This is achieved with a PUT request to the resource. Additional argument
`abort` can be provided in the request which, when true, will execute an abort script
that will send Abort command to the sub-array device. The default value of `abort` is
False. ::

    tangodev@buster:~/ska/ska-oso-oet$ curl -i -H "Content-Type: application/json" -X PUT -d '{"abort": true, "state": "STOPPED"}' http://localhost:5000/ska-oso-oet/oet/api/v1/procedures/2
    HTTP/1.0 200 OK
    Content-Type: application/json
    Content-Length: 467
    Server: Werkzeug/0.16.0 Python/3.7.3
    Date: Wed, 15 Jan 2020 10:14:09 GMT
    {"abort_message":"Successfully stopped script with ID 2 and aborted subarray activity "}

Listen to OET events
--------------------
The session below lists all events published by oet scripts. This
example shows two events, #1 request to available procedures #2 get the details of all the created procedures ::

    tangodev@buster:~/ska/ska-oso-oet$ curl -i http://localhost:5000/ska-oso-oet/oet/api/v1/stream
    HTTP/1.0 200 OK
    Content-Type: text/event-stream; charset=utf-8
    Connection: close
    Server: Werkzeug/1.0.1 Python/3.7.3
    Date: Mon, 02 Nov 2020 06:57:40 GMT

    data:{"msg_src": "FlaskWorker", "pids": null, "topic": "request.procedure.list"}
    id:1605017762.46912

    data:{"msg_src": "SESWorker", "result": [], "topic": "procedure.pool.list"}
    id:1605017762.46912

    data:{"msg_src": "FlaskWorker", "cmd": {"py/object": "oet.procedure.application.application.PrepareProcessCommand", "script_uri": "file://scripts/eventbus.py", "init_args": {"py/object": "oet.procedure.domain.ProcedureInput", "args": {"py/tuple": []}, "kwargs": {"subarray_id": 1}}}, "topic": "request.procedure.create"}
    id:1605017784.1536236

    data:{"msg_src": "SESWorker", "result": {"py/object": "oet.procedure.application.application.ProcedureSummary", "id": 1, "script_uri": "file://scripts/eventbus.py", "script_args": {"init": {"py/object": "oet.procedure.domain.ProcedureInput", "args": {"py/tuple": []}, "kwargs": {"subarray_id": 1}}, "run": {"py/object": "oet.procedure.domain.ProcedureInput", "args": {"py/tuple": []}, "kwargs": {}}}, "history": {"py/object": "oet.procedure.domain.ProcedureHistory", "process_states": {"py/reduce": [{"py/type": "collections.OrderedDict"}, {"py/tuple": []}, null, null, {"py/tuple": [{"py/tuple": [{"py/reduce": [{"py/type": "oet.procedure.domain.ProcedureState"}, {"py/tuple": [1]}]}, 1605017786.0569353]}]}]}, "stacktrace": null}, "state": {"py/id": 5}}, "topic": "procedure.lifecycle.created"}
    id:1605017784.1536236


.. |br| raw:: html

      <br>
