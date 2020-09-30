.. _rest-api:

********
Rest API
********

A ‘Procedure’ represents a script along with its load-time arguments and
runtime arguments. The REST API operates on procedures.

The workflow for the script execution service in PI5 is to:

* Load a requested Python script(s) ready for execution;
* When requested, start execution of the requested script.

It is not necessary to abort script execution this PI.

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
| POST        | /api/v1/procedures      | **Prepare a new procedure**         |
|             |                         | Loads the requested script and      |
|             |                         | prepares it for execution           |
+-------------+-------------------------+-------------------------------------+
| PUT         | /api/v1/procedures/<id> | **Modify a procedure**              |
|             |                         | Modifies the state of a prepared    |
|             |                         | procedure. This can be used to      |
|             |                         | start execution by setting the      |
|             |                         | ‘state’ procedure attribute to      |
|             |                         | ``RUNNING``.                        |
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
|             |            | a call to init(1,2,3,subarray=1)::                                   |
|             |            |                                                                      |
|             |            |    "script_args": {                                                  |
|             |            |      "init": {                                                       |
|             |            |        "args": [                                                     |
|             |            |          1,                                                          |
|             |            |          2,                                                          |
|             |            |          3                                                           |
|             |            |        ],                                                            |
|             |            |        "kwargs": {                                                   |
|             |            |          "subarray": "1"                                             |
|             |            |        }                                                             |
|             |            |      }                                                               |
|             |            |    }                                                                 |
+-------------+------------+----------------------------------------------------------------------+
| state       | str        | Script execution state: CREATED, RUNNING, STOPPED, COMPLETED,        |
|             |            | FAILED.                                                              |
+-------------+------------+----------------------------------------------------------------------+
| history     | object     | history contains a Dict of process_history and stacktrace.           |
|             |            |                                                                      |
|             |            | process_history which contains a Dict of ProcedureStates and         |
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
``init(subarray=1, sb_uri=’file:///path/to/scheduling_block_123.json’)``. The
script is ready to execute but is not yet executing, as shown by its state
being `CREATED``::

    {
        "script_args": {
          "init": {
            "args": [],
            "kwargs": {
              "sb_uri": "file:///path/to/scheduling_block_123.json",
              "subarray": 1
            }
          },
          "run": {
            "args": [],
            "kwargs": {}
          }
        },
        "script_uri": "file:///path/to/observing_script.py",
        "history": {
            "process_history": {
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

    tangodev@buster:~/ska/observation-execution-tool$ curl -i -H "Content-Type: application/json" -X POST -d '{"script_uri":"file:///path/to/observing_script.py", "script_args": {"init": { "kwargs": {"subarray": 1, "sb_uri": "file:///path/to/scheduling_block_123.json"} } }}' http://localhost:5000/api/v1.0/procedures
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
              "subarray": 1
            }
          },
          "run": {
            "args": [],
            "kwargs": {}
          }
        },
        "script_uri": "file:///path/to/observing_script.py",
        "history": {
            "process_history": {
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
              "process_history": {
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
                "subarray": 1
              }
            },
            "run": {
              "args": [],
              "kwargs": {}
            }
          },
          "script_uri": "file:///path/to/observing_script.py",
          "history": {
               "process_history": {
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
            "process_history": {
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
              "subarray": 1
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
            "process_history": {
                "CREATED": 1601463545.7789885,
                "RUNNING": 1601463545.7789997
             },
            "stacktrace": null
        }
        "state": "RUNNING",
        "uri": "http://localhost:5000/api/v1.0/procedures/2"
      }
    }

