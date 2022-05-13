.. _architecture_backend_module_execution:

*****************************************
OET backend module view: Script Execution
*****************************************

Primary Presentation
====================

.. figure:: diagrams/export/backend_module_execution.svg
   :align: center

   Major classes responsible for the execution and management of user scripts.


Elements and their properties
=============================

Components
----------

.. list-table::
   :widths: 15 85
   :header-rows: 1

   * - Component
     - Description
   * - Environment
     - Environment is a dataclass that holds the information required to identify a Python virtual environment and its
       location on disk. In addition, it holds synchronisation primitives to avoid race conditions between multiple
       requests to create the same environment, as would be the case for multiple requests to create virtual
       environments for the same git project and git commit hash.
   * - EnvironmentManager
     - EnvironmentManager is responsible for creating and managing Environments, the custom Python virtual environments
       in which a user script that requiring a non-default environment runs. Typically, this is the case for a request
       to run a script located in a git repository, where the request requires a more recent version of the
       ska-oso-scripting library or control scripts than was packaged with the OET.
       |br|
       |br|
       Environment creation can be expensive, typically taking 20-30 seconds to ready a new ska-oso-scripting
       environment and with all-new dependencies. For this reason, EnvironmentManager is designed to allow virtual
       environments to be shared for script execution requests that target the same git repository and commit, as
       uniquely identified by the git commit hash. EnvironmentManager currently has no policy for deleting virtual
       environments, and the number of virtual environments could in principle increase unbounded manner. A policy of
       maintaining all active environments and maintaining a maximum of _n_ inactive environments is expected to be
       implemented.
   * - MainContext
     - MainContext is the parent context for a set of worker processes that communicate via message queues. It defines
       a consistent architecture for event-based communication between Python processes and consistent behaviour for
       POSIX signal handling and process management.
       |br|
       |br|
       MainContext is responsible for routing messages between the ProcWorkers created within the scope of a
       MainContext. MainContext is also responsible for managing the termination of the child processes, first
       requesting that the child process co-operate and stop execution cleanly, before escalating and using increasingly
       forceful means to terminate unresponsive processes (e.g., SIGINT, then SIGHUP). Lastly, MainContext is responsible
       for the correct management of the Python multiprocessing primitives created within the scope of the MainContext
       that are used for inter-process communication and synchronisation.
   * - Proc
     - Proc represents a child Python process of a MainContext.
       |br|
       |br|
       Proc instances exist in the scope of a MainContext instance and in the same OS process as the parent MainContext.
       Procs are the MainContext's link to the ProcWorkers running in an independent operating system process with an
       independent Python interpreter. Every ProcWorker running in a child process is associated with one Proc.
       |br|
       |br|
       Each Proc is responsible for bootstrapping its ProcWorker and managing its lifecycle. Proc arranges for an
       instance of its referenced ProcWorker class to be initialised and run in a new child Python interpreter. Proc
       monitors the status of the creation process. If ProcWorker startup does not complete successfully, Proc will
       forcibly terminate the child process and report the error.
       |br|
       |br|
       Proc is able to terminate its associated ProcWorker, first by giving the ProcWorker chance to co-operatively
       exit by setting a shutdown event monitored by the ProcWorker. If the ProcWorker exit within a defined grace
       period set, Proc will forcibly terminate the ProcWorker's process.
       |br|
       |br|
       Proc does not contain any business logic or application-specific code, which should be contained in the
       ProcWorker - or more likely, a subclass of ProcWorker.
   * - ProcessManager
     - ProcessManager is the parent for all script execution processes. Specifically, it is the parent of all the
       ScriptWorker instances that run user code in a child Python process. ProcessManager is responsible for launching
       ScriptWorker processes and communicating relaying requests such as 'load user script *X* from git repository
       *Y*' 'run main() function' or 'stop execution' to the running scripts.
       |br|
       |br|
       As the parent of the script execution processes, ProcessManager has the power to forcibly terminate a
       ScriptWorker if it fails to respond to a shutdown request. This power is used when 'abort execution' is called
       to ensure that the script does not continue to send telescope control commands. Currently, a 'hard abort' is
       implemented that in effect does a 'kill -9' on the script. Introduction of a less abrupt 'soft abort' request
       that asks the script to co-operate in terminating execution is planned but not yet implemented.
       |br|
       |br|
       ProcessManager currently maintains its own event bus - that is, it's own MainContext - and is responsible for
       relaying script events issued by the ScriptWorker or user script through to the MainContext monitored by the
       rest of the system. This responsibility is likely to be removed in a future refactoring as the OET consolidates
       on a single event bus.
       |br|
       |br|
       ProcessManager is aware of the current state of ScriptWorkers it owns but does not maintain a state history,
       which as a property spanning multiple transactions is the responsibility of the ScriptExecutionService.
   * - ProcWorker
     - ProcWorker is a template class for code that should execute in a child Python interpreter process.
       |br|
       |br|
       ProcWorker contains the boilerplate code required to set up a well-behaved child process. It handles starting
       the process, connecting signal handlers, signalling the parent that startup completed, etc. ProcWorker does not
       contain any business logic, which should be defined in a subclass of ProcWorker.
   * - ScriptExecutionService
     - ScriptExecutionService provides the high-level API for the script execution domain, presenting methods that
       'start script _Y_' or 'run method _Y_ of user script _Z_'. The ScriptExecutionService orchestrates control of the
       ProcessManager and associated domain objects in order to satisfy an API request.
       |br|
       |br|
       In addition to its primary responsibility of triggering actions in response to API calls, ScriptExecutionService
       is also responsible for recording script execution history, which it achieves by monitoring for and recording script
       lifecycle change events. ScriptExecutionService manages the history state so that the number of records does not
       increase in an unbounded manner (currently, history is maintained for all active scripts and a maximum of 10
       inactive scripts (=any script that is complete).
       ScriptExecutionService provides a presentation model of a script and its
       execution history, which can be formatted for presentation via the REST service and CLI. This presentation model
       is called a ProcedureSummary.
   * - ScriptWorker
     - ScriptWorker is a class that can loads a user script in a child process, running functions of that user script on
       request.
       |br|
       |br|
       ScriptWorker is a ProcWorker that loops over messages received on a message queue, taking an appropriate action
       for every item received on that queue. It responds to four types of messages:

        #. clone a git project, installing that project into a Python virtual environment if required
        #. load a user script in this process
        #. run a named function of the user script in this process
        #. publish a message emitted by another OET component within this process


Context
=======

.. figure:: diagrams/export/backend_candc_context.svg
   :align: center


Variability Guide
=================

N/A

Rationale
=========


.. |br| raw:: html

      <br>
