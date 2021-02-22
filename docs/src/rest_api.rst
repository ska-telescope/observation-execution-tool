.. _rest-api:

********
REST API
********

A ‘Procedure’ represents a script along with its load-time arguments and
runtime arguments. The REST API operates on procedures.

The workflow for the script execution service is to:

* Load a requested Python script(s) ready for execution;
* When requested, start execution of the requested script;
* Abort the script mid-execution if requested with an option to send the abort command to sub-array.

This workflow has been mapped to the following REST API:

+-------------+-------------------------+-------------------------------------+
| HTTP Method | Resource URL            | Description                         |
+=============+=========================+=====================================+
| GET         | /api/v1/procedures      | **List procedures**:                |
|             |                         | Return the collection of all        |
|             |                         | prepared and running procedures     |
+-------------+-------------------------+-------------------------------------+
| GET         | /api/v1/procedures/<id> | Return a procedure definition       |
+-------------+-------------------------+-------------------------------------+
| GET         | /api/v1/stream          | **Streaming real time oet events**: |
|             |                         | Return a real time oet events       |
|             |                         | published by scripts                |
+-------------+-------------------------+-------------------------------------+
| POST        | /api/v1/procedures      | **Prepare a new procedure**         |
|             |                         | Loads the requested script and      |
|             |                         | prepares it for execution           |
+-------------+-------------------------+-------------------------------------+
| PUT         | /api/v1/procedures/<id> | **Modify a procedure**              |
|             |                         | Modifies the state of a prepared    |
|             |                         | procedure. This can be used to      |
|             |                         | start execution by setting the      |
|             |                         | ‘state’ procedure attribute to      |
|             |                         | ``RUNNING`` or stop execution by    |
|             |                         | setting ‘state’ to ``STOPPED``.     |
+-------------+-------------------------+-------------------------------------+

Procedures are defined as JSON objects with the following fields:

+-------------+------------+----------------------------------------------------------------------+
| Field       | JSON Type  | Description                                                          |
+=============+============+======================================================================+
| uri         | string     | Read-only procedure URI. Defined by server on procedure creation.    |
+-------------+------------+----------------------------------------------------------------------+
| script_uri  | string     | URI of the script to execute, e.g., file:///path/to/obsscript.py     |
+-------------+------------+----------------------------------------------------------------------+
| script_args | object     | **TO BE REFINED!** Dict of input arguments to provide to methods in  |
|             |            | the script. Only two methods are recognised at the moment: ‘init’,   |
|             |            | called at script creation time, and ‘run’, called to commence script |
|             |            | execution.                                                           |
|             |            |                                                                      |
|             |            | Keys are the name of the script method, values are dicts with two    |
|             |            | keys (‘args’ and ‘kwargs’) for positional arguments and              |
|             |            | keyword/value arguments respectively. For example, below represents  |
|             |            | a call to init(1,2,3,subarray_id=1)::                                |
|             |            |                                                                      |
|             |            |    "script_args": {                                                  |
|             |            |      "init": {                                                       |
|             |            |        "args": [                                                     |
|             |            |          1,                                                          |
|             |            |          2,                                                          |
|             |            |          3                                                           |
|             |            |        ],                                                            |
|             |            |        "kwargs": {                                                   |
|             |            |          "subarray_id": "1"                                          |
|             |            |        }                                                             |
|             |            |      }                                                               |
|             |            |    }                                                                 |
+-------------+------------+----------------------------------------------------------------------+
| state       | str        | Script execution state: CREATED, RUNNING, STOPPED, COMPLETED,        |
|             |            | FAILED.                                                              |
+-------------+------------+----------------------------------------------------------------------+
| history     | object     | history contains a Dict of process_states and stacktrace.            |
|             |            |                                                                      |
|             |            | process_states which contains a Dict of ProcedureStates and          |
|             |            | timestamps for each state (e.g. {'CREATED': 18392174.543,            |
|             |            | 'RUNNING': 18392143.546, 'COMPLETED': 183925456.744}).               |
|             |            |                                                                      |
|             |            | stacktrace which is None on default and will be populated with       |
|             |            | the stacktrace from the script if script execution raises an         |
|             |            | exception.                                                           |
|             |            |                                                                      |
+-------------+------------+----------------------------------------------------------------------+

Below is a JSON representation of an example procedure resource. This resource
(located at URI http://localhost:5000/api/v1.0/procedures/1), represents a
script (located on disk at /path/to/observing_script.py), that has been loaded
and its initialisation method called with two arguments (e.g, the script init
function was called as
``init(subarray_id=1, sb_uri=’file:///path/to/scheduling_block_123.json’)``. The
script is ready to execute but is not yet executing, as shown by its state
being `CREATED``::

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
        "script_uri": "file:///path/to/observing_script.py",
        "history": {
            "process_states": {
                 "CREATED": 1601463545.7789776
                },
            "stacktrace": null
            },
        "state": "CREATED",
        "uri": "http://localhost:5000/api/v1.0/procedures/1"
    }

Examples
========

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

    tangodev@buster:~/ska/observation-execution-tool$ curl -i -H "Content-Type: application/json" -X POST -d '{"script_uri":"file:///path/to/observing_script.py", "script_args": {"init": { "kwargs": {"subarray_id": 1, "sb_uri": "file:///path/to/scheduling_block_123.json"} } }}' http://localhost:5000/api/v1.0/procedures
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
        "script_uri": "file:///path/to/observing_script.py",
        "history": {
            "process_states": {
                "CREATED": 1601463545.7789776
                },
            "stacktrace": null
        },
        "state": "CREATED",
        "uri": "http://localhost:5000/api/v1.0/procedures/2"
      }
    }

Listing all procedures
----------------------
The session below lists all procedures, both running and non-running. This
example shows two procedures have been created: procedure #1 that will run
resource_allocation.py, and procedure #2 that will run observing_script.py::

    tangodev@buster:~/ska/observation-execution-tool$ curl -i http://localhost:5000/api/v1.0/procedures
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
          "script_uri": "file:///path/to/resource_allocation.py",
          "history": {
              "process_states": {
                   "CREATED": 1601463545.7789776
                },
              "stacktrace": null
		  },
          "state": "CREATED",
          "uri": "http://localhost:5000/api/v1.0/procedures/1"
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
          "script_uri": "file:///path/to/observing_script.py",
          "history": {
               "process_states": {
                   "CREATED": 1601463545.7789885
                  },
               "stacktrace": null
          },
          "state": "CREATED",
          "uri": "http://localhost:5000/api/v1.0/procedures/2"
        }
      ]
    }

Listing one procedure
---------------------
A specific procedure can be listed by a GET request to its specific URI. The
session below lists procedure #1::

    tangodev@buster:~/ska/observation-execution-tool$ curl -i http://localhost:5000/api/v1.0/procedures/1
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
        "script_uri": "file:///path/to/resource_allocation.py",
        "history": {
            "process_states": {
                "CREATED": 1601463545.7789776
                },
            "stacktrace": null
        },
        "state": "CREATED",
        "uri": "http://localhost:5000/api/v1.0/procedures/1"
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

    tangodev@buster:~/ska/observation-execution-tool$ curl -i -H "Content-Type: application/json" -X PUT -d '{"script_args": {"run": {"kwargs": {"scan_duration": 14.0}}}, "state": "RUNNING"}' http://localhost:5000/api/v1.0/procedures/2
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
        "script_uri": "file:///path/to/observing_script.py",
        "history": {
            "process_states": {
                "CREATED": 1601463545.7789885,
                "RUNNING": 1601463545.7789997
             },
            "stacktrace": null
        }
        "state": "RUNNING",
        "uri": "http://localhost:5000/api/v1.0/procedures/2"
      }
    }


Aborting process execution
--------------------------
The signal to abort script mid-execution is to change the state of a procedure to
``STOPPED``. This is achieved with a PUT request to the resource. Additional argument
`abort` can be provided in the request which, when true, will execute an abort script
that will send Abort command to the sub-array device. The default value of `abort` is
False. ::

    tangodev@buster:~/ska/observation-execution-tool$ curl -i -H "Content-Type: application/json" -X PUT -d '{"abort": true, "state": "STOPPED"}' http://localhost:5000/api/v1.0/procedures/2
    HTTP/1.0 200 OK
    Content-Type: application/json
    Content-Length: 467
    Server: Werkzeug/0.16.0 Python/3.7.3
    Date: Wed, 15 Jan 2020 10:14:09 GMT
    {"abort_message":"Successfully stopped script with ID 2 and aborted subarray activity "}

When an error occurs
--------------------
If there is a mistake in the User input it is desirable that the API produces 
errors in a consistent computer-readable way.

The session below attempts to list a procedure which does not exist::

    tangodev@buster:~/ska/observation-execution-tool$ curl -i http://localhost:5000/api/v1.0/procedures/4
    HTTP/1.0 404 NOT FOUND
    Content-Type: application/json
    Content-Length: 103
    Server: Werkzeug/1.0.1 Python/3.7.3
    Date: Thu, 18 Feb 2021 17:40:30 GMT

    {"error": "404 Not Found", "type": "ResourceNotFound", "Message": "No information available for PID=4"}

Listen real time oet events
---------------------------
The session below lists all events published by oet scripts. This
example shows two events, #1 request to available procedures #2 get the details of all the created procedures ::

    tangodev@buster:~/ska/observation-execution-tool$ curl -i http://localhost:5000/api/v1.0/stream
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


