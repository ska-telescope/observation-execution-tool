.. _architecture_backend_module_execution:

**********************************
Module view: SB Activity Execution
**********************************

.. note::
    Diagrams are embedded as SVG images. If the text is too small, please use your web browser to zoom in to the images,
    which should be magnified without losing detail.

This view is a module view depicting the key components involved in SB activity execution; that is, requesting
an activity described by a Scheduling Block to be executed.


Primary Presentation
====================

.. figure:: diagrams/export/backend_module_script_execution_primary_activity.svg
   :align: center

   Major classes responsible for the execution and management of activities.


Element Catalogue
=================

Elements and their properties
-----------------------------

.. list-table::
   :widths: 15 85
   :header-rows: 1

   * - Component
     - Description
   * - :class:`~ska_oso_oet.procedure.application.ActivityService`
     - ProcedureInput captures the anonymous positional arguments and named keyword arguments for a Python function
       call. ProcedureInput is used in the presentation model to help describe historic function calls as well as
       in the PrepareProcessCommand and StartProcessCommand to define the arguments for an upcoming call.
   * - :class:`~ska_oso_oet.procedure.domain.ProcedureState`
     - ProcedureState is an enumeration defining the states that a Procedure (a child ScriptWorker process running a
       Python script) can be in. The states are:

        * ``CREATING``: child process is being created but is not yet initialised or ready to process other actions.
        * ``IDLE``: child process has been successfully created and is ready to process the next instruction.
        * ``PREP_ENV``: virtual environment for the user script is being prepared and its dependencies installed.
        * ``LOADING``: user script is being retrieved and loaded.
        * ``READY``: user script is fully initialised and ready to run.
        * ``RUNNING``: a function of the user script is being run.
        * ``COMPLETE``: the user script has completed successfully and the child process exited cleanly.
        * ``STOPPED``: the user script was forcibly terminated
        * ``FAILED``: the script process terminated due to an exception.
        * ``UNKNOWN``: script termination failed, leaving the script in an unknown state and effectively unmanaged
   * - :class:`~ska_oso_oet.procedure.domain.ProcessManager`
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
   * - :class:`~ska_oso_oet.mptools.ProcWorker`
     - ProcWorker is a template class for code that should execute in a child Python interpreter process.
       |br|
       |br|
       ProcWorker contains the boilerplate code required to set up a well-behaved child process. It handles starting
       the process, connecting signal handlers, signalling the parent that startup completed, and monitoring whether
       shutdown has been requested. ProcWorker does not contain any business logic, implementing a simple loop that
       repeatedly runs the abstract `main_func()` function for as long as the shutdown event is not set.
   * - Queue
     - Queue is a class that implements a multi-consumer, multi-producer FIFO queue that can be shared between Python
       processes. Queue is part of the standard Python library.
   * - :class:`~ska_oso_oet.mptools.QueueProcWorker`
     - QueueProcWorker is a ProcWorker that loops over items received on a message queue, calling the abstract
       `main_func()` function for every item received. Together with the ProcWorker base class functionality,
       QueueProcWorker will call `main_func()` for every event received for as long as the shutdown event is not set.
   * - :class:`~ska_oso_oet.procedure.application.application.ScriptExecutionService`
     - ScriptExecutionService provides the high-level API for the script execution domain, presenting methods that
       'start script _Y_' or 'run method _Y_ of user script _Z_'. The ScriptExecutionService orchestrates control of the
       ProcessManager and associated domain objects in order to satisfy an API request.
       |br|
       |br|
       In addition to its primary responsibility of triggering actions in response to API calls, ScriptExecutionService
       is also responsible for recording script execution history and providing a summary of process state.
       See :doc:`architecture_backend_module_ui` for more information.
   * - :class:`~ska_oso_oet.procedure.domain.ScriptWorker`
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


Element Interfaces
------------------

The major public interface in these interactions is the ScriptExecutionService API. For more information on this
interface, please see the API documentation for
:py:class:`~ska_oso_oet.procedure.application.application.ScriptExecutionService`.

Element Behaviour
-----------------

ScriptExecutionService
~~~~~~~~~~~~~~~~~~~~~~

The sequence diagram below gives a high-level overview of how the
:class:`~ska_oso_oet.procedure.application.application.ScriptExecutionService` controls objects in the domain module to
meet requests to prepare, start, and stop user script execution.

.. figure:: diagrams/export/backend_module_ui_sequence_ses.svg
   :align: center

|br|

ScriptExecutionService.prepare
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The diagram below gives more detail on how the domain layer handles a request to prepare a script for execution.

.. figure:: diagrams/export/backend_module_ui_sequence_ses_prepare.svg
   :align: center

|br|

ScriptWorker
~~~~~~~~~~~~

The diagram below illustrates how a :class:`~ska_oso_oet.procedure.domain.ScriptWorker` is created and how it
communicates startup success with the parent process.

.. figure:: diagrams/export/backend_module_ui_sequence_scriptworker.svg
   :align: center

|br|

ScriptWorker.main_loop
~~~~~~~~~~~~~~~~~~~~~~

The diagram below depicts the main :class:`~ska_oso_oet.procedure.domain.ScriptWorker` message loop, illustrating how
the various messages from the parent :class:`~ska_oso_oet.procedure.domain.ProcessManager` are handled by child
:class:`~ska_oso_oet.procedure.domain.ScriptWorker`.

.. figure:: diagrams/export/backend_module_ui_sequence_scriptworker_main_loop.svg
   :align: center

|br|

Context Diagram
===============

.. figure:: diagrams/export/backend_module_execution_context.svg
   :align: center


|br|

Variability Guide
=================

N/A

Rationale
=========

N/A


.. |br| raw:: html

      <br>
