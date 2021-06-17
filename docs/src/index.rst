.. skeleton documentation master file, created by
   sphinx-quickstart on Thu May 17 15:17:35 2018.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.


.. HOME SECTION ==================================================

.. Hidden toctree to manage the sidebar navigation.

.. toctree::
  :maxdepth: 1
  :caption: Home
  :hidden:

  rest_server
  rest_client
  rest_api

.. COMMUNITY SECTION ==================================================

.. Hidden toctree to manage the sidebar navigation.

.. toctree::
  :maxdepth: 1
  :caption: Public API Documentation
  :hidden:

==========================
Observation Execution Tool
==========================

Project description
===================

The `ska-oso-oet` project contains the code for the Observation Execution Tool (OET), the
application which provides on-demand Python script execution for the SKA.

Overview
========
The OET consists of a script execution engine, which loads specified scripts
and runs them in child Python processes, and a REST layer which makes the
API for the script execution engine available via REST over HTTP.

The REST layer is made up of two components that work together to provide the
remote script execution functionality:

- The OET :doc:`rest_server` maintains a list of the scripts that have been
  loaded and their current state. The server implements the interface specified
  by the OET :doc:`rest_api`.
- The OET :doc:`rest_client` provides a Command Line Interface (CLI) to the
  OET :doc:`rest_server`. It does this by translating and communicating HTTP
  messages to and from the server.

.. note::
   SKA control scripts are not packaged as part of this project. The repository
   of observing scripts executed by the OET can be found in the
   `OET Scripts <https://developer.skatelescope.org/projects/oet-scripts/en/latest/index.html>`_
   project.

Quickstart
==========
This project is structured to use Docker containers for development and
testing so that the build environment, test environment and test results are
all completely reproducible and are independent of host environment. It uses
``make`` to provide a consistent UI (see `Makefile targets`_).

Build a new Docker image for the OET with:

::

  make build

Execute the test suite and lint the project with:

::

  make test
  make lint

Makefile targets
================
This project contains a Makefile which acts as a UI for building Docker
images, testing images, and for launching interactive developer environments.
The following make targets are defined:

+-----------------+------------------------------------------------+
| Makefile target | Description                                    |
+=================+================================================+
| build           | Build a new application image                  |
+-----------------+------------------------------------------------+
| test            | Test the application image                     |
+-----------------+------------------------------------------------+
| lint            | Lint the application image                     |
+-----------------+------------------------------------------------+
| prune           | Delete stale Docker images for this project    |
+-----------------+------------------------------------------------+
| interactive     | Launch a minimal Tango system (including the   |
|                 | device under development), mounting the source |
|                 | directory from the host machine inside the     |
|                 | container                                      |
+-----------------+------------------------------------------------+
| push            | Push the application image to the Docker       |
|                 | registry                                       |
+-----------------+------------------------------------------------+
| up              | launch the development/test container service  |
|                 | on which this application depends              |
+-----------------+------------------------------------------------+
| down            | stop all containers launched by 'make up' and  |
|                 | 'make interactive'                             |
+-----------------+------------------------------------------------+
| rest            | start the OET REST server                      |
+-----------------+------------------------------------------------+
| help            | show a summary of the makefile targets above   |
+-----------------+------------------------------------------------+

Creating a new application image
--------------------------------
``make build`` target creates a new Docker image for the application based
on the 'ska-python-runtime' image. To optimise final image size and to support
the inclusion of C extension Python libraries such as pytango, the application
is built inside an intermediate Docker image which includes compilers and
cached eggs and wheels for commonly-used Python libraries
('ska-python-builder'). The resulting Python environment from this
intermediate stage is copied into a final image which extends a minimal SKA
Python runtime environment ('ska-python-runtime'), to give the final Docker
image for this application.

Interactive development using containers
----------------------------------------
``make interactive`` launches an interactive session using the application
image, mounting the project source directory at /app inside the container.
This allows the container to run code from the local workspace. Any changes
made to the project source code will immediately be seen inside the container.

Test execution
--------------
``make test`` runs the application test procedure defined in
test-harness/Makefile in a temporary container. The Makefile example for
this project runs 'python setup.py test' and copies the resulting output and
test artefacts out of the container and into a 'build' directory, ready for
inclusion in the CI server's downloadable artefacts.

REST server
-----------
``make rest`` starts the OET REST server. Details of the REST API can be
found in :doc:`rest_api`. Instructions on how to use the REST client
can be found here: :doc:`rest_client`.

Feature flags
-------------
OET feature flags are configured via environment variables and configuration
files. The configuration file, oet.ini, can be located either in the user's
home directory, or the root of the installation folder.

Feature flags are read in this order:

#. environment variable;
#. oet.ini configuration file;
#. default flag value as specified in OET code.

Available feature flags are:

+----------------------+-------------------+---------+----------------------------+---------+
| environment variable | oet.ini setting   | Type    | Description                | Default |
+======================+===================+=========+============================+=========+
| OET_READ_VIA_PUBSUB  | read_via_pubsub   | Boolean | sets whether pubsub or     | False   |
|                      |                   |         | the alternative, polling,  |         |
|                      |                   |         | is used to read from tango |         |
+----------------------+-------------------+---------+----------------------------+---------+
