.. _how-to-run-test-script.rst:

**********************************
How-to: run demo scripts with CLI
**********************************

As described in previous sections, the OET can be used to run any script from either its filesystem or from a Git repository.
To operate the telescope, these scripts will process SBDefinitions and send commands to TMC devices.

This guide will step through running some basic Hello World scripts and inspecting the outcomes. The idea is that a new
user can familiarise themselves with the OET by doing this, before running real observing scripts that interact with the telescope.

The scripts are defined in the `ska-oso-oet Helm chart <https://gitlab.com/ska-telescope/oso/ska-oso-oet/-/tree/master/charts/ska-oso-oet/data?ref_type=heads>`_ and are loaded
into the OET pod via a ConfigMap on deployment into the filesystem location ``/tmp/scripts``.

Run a script as a Procedure
============================

This section runs through an example session in which we will
load two new 'Procedures' using the same script with different input variables.

The ``hello_world_without_sb.py`` can be seen in the link above and will just print some statements.

1. Deploy the OET and access a terminal with the CLI installed
----------------------------------------------------------------

Follow the steps in the previous sections to deploy the OET server and install and configure the OET CLI to interact with this server. The simplest way to do this
is to run ``make k8s-install-chart`` use the CLI that is installed in the OET image, which will connect to the server running in the same pod. To access a terminal in this pod and check the CLI and scripts are available:

.. code-block:: console

    # Exec into the OET pod
    $ kubectl exec -it ska-oso-oet-rest-test-0 -n ska-oso-oet -- bash

    # You should now be at a terminal inside the pod. First, check the OET CLI is available and see the help docs
    $ oet --help
    NAME
        oet - OET command-line interface.
    ...

    # Now check the scripts are available in the filesystem
    $ ls /tmp/scripts
    hello_world_with_sb.py  hello_world_without_sb.py  low_sb_example.json  mid_sb_example.json

2. Create the two Procedures
-----------------------------

.. code-block:: console

    # Create the first Procedure with no extra args
    $ oet procedure create file:///tmp/scripts/hello_world_without_sb.py
      ID  Script                                         Creation Time        State
    ----  ---------------------------------------------  -------------------  --------
       1  file:///tmp/scripts/hello_world_without_sb.py  2024-10-28 09:13:04  CREATING
     For more details:- oet procedure describe --pid=<id>


    # Create the second Procedure with a kwarg
    $ oet procedure create file:///tmp/scripts/hello_world_without_sb.py --init_arg='hello demo'
      ID  Script                                         Creation Time        State
    ----  ---------------------------------------------  -------------------  --------
       2  file:///tmp/scripts/hello_world_without_sb.py  2024-10-28 09:14:10  CREATING
     For more details:- oet procedure describe --pid=<id>


    # Check the state of the loaded Procedures and see their pid
    $ oet procedure list
      ID  Script                                         Creation Time        State
    ----  ---------------------------------------------  -------------------  -------
       1  file:///tmp/scripts/hello_world_without_sb.py  2024-10-28 09:23:02  READY
       2  file:///tmp/scripts/hello_world_without_sb.py  2024-10-28 09:23:34  READY
     For more details:- oet procedure describe --pid=<id>


3. Run the Procedures
----------------------

.. code-block:: console

    # Run the first Procedure with no extra args
    $ oet procedure start --pid=1
      ID  Script                                         Creation Time        State
    ----  ---------------------------------------------  -------------------  -------
       1  file:///tmp/scripts/hello_world_without_sb.py  2024-10-28 09:23:02  READY
     For more details:- oet procedure describe --pid=<id>

    Events
    ------

    - Script message: pretending to execute scan 2/10
    - Script message: pretending to execute scan 3/10
    - Script message: pretending to execute scan 4/10
    - Script message: pretending to execute scan 5/10
    - Script message: pretending to execute scan 6/10
    - Script message: pretending to execute scan 7/10
    - Script message: pretending to execute scan 8/10
    - Script message: pretending to execute scan 9/10
    - Script message: Script complete

    # NOTE: This will keep the event stream open in terminal. Use Ctrl+C to exit.

    # See details on the Procedure progress
    $ oet procedure describe --pid=1
      ID  Script                                         URI
    ----  ---------------------------------------------  ---------------------------------------------------------------------
       1  file:///tmp/scripts/hello_world_without_sb.py  http://ska-oso-oet-rest-test:5000/ska-oso-oet/oet/api/v6/procedures/1

    Time                        State
    --------------------------  ------------
    2024-10-28 09:23:02.742257  CREATING
    2024-10-28 09:23:02.743366  IDLE
    2024-10-28 09:23:02.744641  LOADING
    2024-10-28 09:23:02.745737  IDLE
    2024-10-28 09:23:02.745944  INITIALISING
    2024-10-28 09:23:02.746739  READY
    2024-10-28 09:24:41.135927  RUNNING 1
    2024-10-28 09:24:50.153699  READY
    2024-10-28 09:24:50.174847  COMPLETE

      Index  Method    Arguments    Keyword Arguments
    -------  --------  -----------  -------------------
          1  init      []           {'subarray_id': 1}
          2  main      []           {}


    # Run the second Procedure with another kwarg
    $ oet procedure start --pid=2 --another_kwarg=7
    ID  Script                                         Creation Time        State
    ----  ---------------------------------------------  -------------------  -------
       2  file:///tmp/scripts/hello_world_without_sb.py  2024-10-28 09:23:34  READY
     For more details:- oet procedure describe --pid=<id>

    Events
    ------

    - Script message: pretending to execute scan 2/10
    - Script message: pretending to execute scan 3/10
    - Script message: pretending to execute scan 4/10
    - Script message: pretending to execute scan 5/10
    - Script message: pretending to execute scan 6/10
    - Script message: pretending to execute scan 7/10
    - Script message: pretending to execute scan 8/10
    - Script message: pretending to execute scan 9/10
    - Script message: Script complete

    $ oet procedure describe --pid=2
      ID  Script                                         URI
    ----  ---------------------------------------------  ---------------------------------------------------------------------
       2  file:///tmp/scripts/hello_world_without_sb.py  http://ska-oso-oet-rest-test:5000/ska-oso-oet/oet/api/v6/procedures/2

    Time                        State
    --------------------------  ------------
    2024-10-28 09:23:34.689789  CREATING
    2024-10-28 09:23:34.690307  IDLE
    2024-10-28 09:23:34.692724  LOADING
    2024-10-28 09:23:34.692866  IDLE
    2024-10-28 09:23:34.693018  INITIALISING
    2024-10-28 09:23:34.693177  READY
    2024-10-28 09:51:31.225424  RUNNING 1
    2024-10-28 09:51:40.241787  READY
    2024-10-28 09:51:40.262797  COMPLETE

      Index  Method    Arguments    Keyword Arguments
    -------  --------  -----------  --------------------------------------------
          1  init      []           {'init_arg': 'hello demo', 'subarray_id': 1}
          2  main      []           {'another_kwarg': 7}


Note the second describe output shows the kwargs passed via the CLI.

If the procedure failed, then the stack trace will also be displayed.

Run an Activity
================

This section steps through running an 'Activity' that is defined inside an SBDefinition. The 'Activity' should
define where to find the script, as described in other sections. The OET will pull the SBDefinition from the ODA
by its identifier, so the SBDefinition needs to be loaded into the ODA during these steps.

1. Deploy the OET and access a terminal with the CLI installed
----------------------------------------------------------------

Follow step 1 in the section above.

2. Load the SBDefinition into the ODA
---------------------------------------

There are two SBDefinitions in the OET Helm chart data directory that are loaded into the OET pod - ``mid_sb_example.json`` and ``low_sb_example.json``.
These both contain an Activity ``example_activity`` that reference the ``hello_world_without_sb.py`` script.

As part of the ``ska-oso-oet-umbrella`` default deployment, the ODA database and REST server are deployed. To upload the SBDefinition to the ODA,
you can either use the SwaggerUI available at ``<KUBE_HOST>/<OET_NAMESPACE>/oda/api/v<ODA_MAJOR_VERSION>/ui/`` from outside the cluster.

Alternatively, from inside the OET pod terminal you can access the ODA API via the Kubernetes service:

.. code-block:: console

    $ curl -X 'POST' 'http://ska-db-oda-rest-test:5000/ska-oso-oet/oda/api/v6/sbds' \
        -H 'accept: application/json' \
        -H 'Content-Type: application/json' \
        -d '@/tmp/scripts/mid_sb_example.json'


The ``sbd_id`` should then be available in the response body - the commands below use ``sbd-t0001-20241028-00008`` but the real value
should be used when you run these commands.

3. Run the Activity
-----------------------

The name of the activity is defined in the SBDefinition you just uploaded to the ODA. The example is called `observe`.

.. code-block:: console

    # Run an Activity, passing some runtime kwargs
    $ oet activity run example_activity sbd-t0001-20241028-00008 --script-args='{"init": {"kwargs": {"subarray_id": 1}}, "run": {"kwargs": {"another_kwarg": 7}}}'
      ID  Activity          SB ID                     Creation Time          Procedure ID  State
    ----  ----------------  ------------------------  -------------------  --------------  -------
       1  example_activity  sbd-t0001-20241028-00008  2024-10-28 11:17:57               3  TODO
     For details on activity:- oet activity describe --aid=<ID>
     For details on script execution:- oet procedure describe --pid=<Procedure ID>

    Events
    ------

    - Script message: Loaded SB with ID sbd-t0001-20241028-00008
    - Script message: pretending to execute scan calibrator scan
    - Script message: pretending to execute scan science scan
    - Script message: Script complete


    # NOTE: This will keep the event stream open in terminal. Use Ctrl+C to exit.

    # Check the state of the Activity and see the aid
    $ oet activity list
      ID  Activity          SB ID                     Creation Time          Procedure ID  State
    ----  ----------------  ------------------------  -------------------  --------------  -------
       1  example_activity  sbd-t0001-20241028-00008  2024-10-28 11:17:57               3  TODO
     For details on activity:- oet activity describe --aid=<ID>


    # See details on the Activity progress
    $ oet activity describe --aid=1
      ID  Activity          SB ID                       Procedure ID  State
    ----  ----------------  ------------------------  --------------  -------
       1  example_activity  sbd-t0001-20241028-00008               3  TODO

    URI                                                                    Prepare Only
    ---------------------------------------------------------------------  --------------
    http://ska-oso-oet-rest-test:5000/ska-oso-oet/oet/api/v6/activities/1  False

    Time                        State
    --------------------------  -------
    2024-10-28 11:17:57.419620  TODO


    Script Arguments
    -----------------------

    Method    Arguments    Keyword Arguments
    --------  -----------  --------------------------------------------------------------------------
    init      []           {'subarray_id': 1}
    main      []           {'sb_json': '/tmp/tmp13n7l51i.json', 'sbi_id': 'sbi-t0001-20241028-00009'}
    run       []           {'another_kwarg': 7}


    For details on script execution related to the activity
    use `oet procedure` commands with the Procedure ID


    # You can also view the details of the script that was ran by the activity
    $ oet procedure describe --pid=3
      ID  Script                                      URI
    ----  ------------------------------------------  ---------------------------------------------------------------------
       3  file:///tmp/scripts/hello_world_with_sb.py  http://ska-oso-oet-rest-test:5000/ska-oso-oet/oet/api/v6/procedures/3

    Time                        State
    --------------------------  ------------
    2024-10-28 11:17:57.431737  CREATING
    2024-10-28 11:17:57.432042  IDLE
    2024-10-28 11:17:57.433590  LOADING
    2024-10-28 11:17:57.436253  IDLE
    2024-10-28 11:17:57.436546  INITIALISING
    2024-10-28 11:17:57.436751  READY
    2024-10-28 11:17:57.440686  RUNNING 1
    2024-10-28 11:17:59.571001  READY
    2024-10-28 11:17:59.592407  COMPLETE

      Index  Method    Arguments    Keyword Arguments
    -------  --------  -----------  --------------------------------------------------------------------------
          1  init      []           {'subarray_id': 1}
          2  main      []           {'sb_json': '/tmp/tmp13n7l51i.json', 'sbi_id': 'sbi-t0001-20241028-00009'}
          3  run       []           {'another_kwarg': 7}


The activity has now been started and will complete without any further
interaction from the user.

If there was an issue with the running of the script, this is best examined with ``oet activity describe`` then ``oet procedure describe``.

Here's what has gone on inside the OET server while you executed these commands:

#. The OET received the command to run the Activity
#. The OET queried the ODA for sbd-t0001-20241028-00008 and loaded it into its filesystem
#. The OET created an SBInstance for the execution in the IDA
#. The OET parsed the activities in the SBDefinition to find the location of the script
#. The script was loaded into a child process, creating a Procedure
#. The Procedure was ran, and the outcome reflected in the Activity


Prepare an Activity, then run the created Procedure
====================================================

This section demonstrates the more advanced use of controlling Activity execution with additional
``oet procedure`` commands. For this we will prepare an Activity without
executing it and use the ``oet procedure`` commands to run the prepared
activity.

This assumes the session has continued from above, so the outputs also contain the first Activity you just ran.

1. Prepare the Activity
-------------------------

.. code-block:: console

    # Run an Activity, passing some runtime kwargs
    $ oet activity run example_activity sbd-t0001-20241028-00008 --prepare-only=True
      ID  Activity          SB ID                     Creation Time          Procedure ID  State
    ----  ----------------  ------------------------  -------------------  --------------  -------
       2  example_activity  sbd-t0001-20241028-00008  2024-10-28 11:21:15               4  TODO
     For details on activity:- oet activity describe --aid=<ID>
     For details on script execution:- oet procedure describe --pid=<Procedure ID>

    Events
    ------

    # Check the state of the Activity and see the aid, noting that the new Activity is in
    # state TODO (will be prepared once OET implemention is finished!)
    $ oet activity list
      ID  Activity          SB ID                     Creation Time          Procedure ID  State
    ----  ----------------  ------------------------  -------------------  --------------  -------
       1  example_activity  sbd-t0001-20241028-00008  2024-10-28 11:17:57               3  TODO
       2  example_activity  sbd-t0001-20241028-00008  2024-10-28 11:21:15               4  TODO
     For details on activity:- oet activity describe --aid=<ID>
     For details on script execution:- oet procedure describe --pid=<Procedure ID>

    # See details on the Activity progress
    $ oet activity describe --aid=2
      ID  Activity          SB ID                       Procedure ID  State
    ----  ----------------  ------------------------  --------------  -------
       2  example_activity  sbd-t0001-20241028-00008               4  TODO

    URI                                                                    Prepare Only
    ---------------------------------------------------------------------  --------------
    http://ska-oso-oet-rest-test:5000/ska-oso-oet/oet/api/v6/activities/2  True

    Time                        State
    --------------------------  -------
    2024-10-28 11:21:15.420109  TODO


    Script Arguments
    -----------------------

    Method    Arguments    Keyword Arguments
    --------  -----------  --------------------------------------------------------------------------
    init      []           {'subarray_id': 1}
    main      []           {'sb_json': '/tmp/tmpm770o00k.json', 'sbi_id': 'sbi-t0001-20241028-00010'}


    For details on script execution related to the activity
    use `oet procedure` commands with the Procedure ID


2. Run the Activity via the Procedure
-----------------------------------------

To run the script of the second activity we need to note the Procedure ID for the activity and use oet procedure commands to run the script:

As this is an advanced use case, we need to replicate the behaviour of the OET Activity domain and pass the sb_json file path
into the script. To find this, ``ls /tmp`` and see the name of the file that was just created. Use that file name instead of the example
shown below.

.. code-block:: console

    # Using the pid from the `oet activity describe` output
    $ oet procedure start --pid=4 --sb_json='/tmp/tmpm770o00k.json'
      ID  Script                                      Creation Time        State
    ----  ------------------------------------------  -------------------  -------
       4  file:///tmp/scripts/hello_world_with_sb.py  2024-10-28 11:28:12  READY
     For more details:- oet procedure describe --pid=<id>

    Events
    ------

    - Script message: Loaded SB with ID sbd-t0001-20241028-00008
    - Script message: pretending to execute scan calibrator scan
    - Script message: pretending to execute scan science scan
    - Script message: Script complete


    # Now see details on the Activity as the Procedure executes
    $ oet activity describe --aid=2
      ID  Activity          SB ID                       Procedure ID  State
    ----  ----------------  ------------------------  --------------  -------
       2  example_activity  sbd-t0001-20241028-00008               4  TODO

    URI                                                                    Prepare Only
    ---------------------------------------------------------------------  --------------
    http://ska-oso-oet-rest-test:5000/ska-oso-oet/oet/api/v6/activities/2  True

    Time                        State
    --------------------------  -------
    2024-10-28 11:28:12.232138  TODO


    Script Arguments
    -----------------------

    Method    Arguments    Keyword Arguments
    --------  -----------  --------------------------------------------------------------------------
    init      []           {'subarray_id': 1}
    main      []           {'sb_json': '/tmp/tmpm770o00k.json', 'sbi_id': 'sbi-t0001-20241028-00011'}


    For details on script execution related to the activity
    use `oet procedure` commands with the Procedure ID


    # You can also view the details of the Procedure
    $ oet procedure describe --pid=4
      ID  Script                                      URI
    ----  ------------------------------------------  ---------------------------------------------------------------------
       4  file:///tmp/scripts/hello_world_with_sb.py  http://ska-oso-oet-rest-test:5000/ska-oso-oet/oet/api/v6/procedures/5

    Time                        State
    --------------------------  ------------
    2024-10-28 11:28:12.243857  CREATING
    2024-10-28 11:28:12.244079  IDLE
    2024-10-28 11:28:12.245650  LOADING
    2024-10-28 11:28:12.246261  IDLE
    2024-10-28 11:28:12.247387  INITIALISING
    2024-10-28 11:28:12.247601  READY
    2024-10-28 11:28:38.745107  RUNNING 1
    2024-10-28 11:28:40.875785  READY
    2024-10-28 11:28:40.896723  COMPLETE

      Index  Method    Arguments    Keyword Arguments
    -------  --------  -----------  ------------------------------------
          1  init      []           {'subarray_id': 1}
          2  main      []           {'sb_json': '/tmp/tmpm770o00k.json'}


To see the contents of the SBInstance, the ``sbi_id`` from the output can be used to query the ODA.


Next steps
==========

This how-to should have given you the basics of executing OET CLI commands to run Activities and the lower level Procedures on an OET server, using a script that is
available on the OET filesystem.

A next test would be to pull a script from Git instead of the filesystem. The commands are mostly the same, but rather than ``file://`` for the script prefix, ``git://`` should be
used, and the extra args used to define the Git repo, branch and script location defined in :doc:`cli` should be used. For example:

.. code-block:: console
  
    $ oet procedure create git://scripts/allocate_and_observe_sb.py --git_repo=https://gitlab.com/ska-telescope/oso/ska-oso-scripting.git --git_branch="test"

After this, you should be ready to use the OET to execute real observing scripts pulled from ska-oso-scripting.