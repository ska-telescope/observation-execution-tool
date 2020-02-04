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
  :caption: Package-name
  :hidden:

  package/guide

==========================
observation-execution-tool
==========================

Project description
===================

This project contains the code for the Observation Execution Tool (OET), the
application which provides high-level scripting facilities and a high-level
scripting UI for the SKA.

Overview
========
The OET is made up of two components that work together to provide the required
functionality:

- The OET :doc:`rest_server` [1]_ maintains a list of the scripts that have been
  loaded and their current state. The server implements the interface specified
  by the OET :doc:`rest_api`.
- The OET :doc:`rest_client` provides a Command Line Interface (CLI) to the 
  OET :doc:`rest_server`. It does this by translating and communicating HTTP 
  messages to and from the server.

.. [1] Representational State Transfer (REST) is an architectural style that
       guarantees interopability between computer systems on the internet.

Quickstart
==========
This project is structured to use Docker containers for development and
testing so that the build environment, test environment and test results are
all completely reproducible and are independent of host environment. It uses
``make`` to provide a consistent UI (see `Makefile targets`_).

Build a new Docker image for the OET with:

::

  make build

Execute the test suite with:

::

  make test


Launch an interactive shell inside a container, with your workspace visible
inside the container:

::

  make interactive

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
| interactive     | Launch a minimal Tango system (including the   |
|                 | device under development), mounting the source |
|                 | directory from the host machine inside the     |
|                 | container                                      |
+-----------------+------------------------------------------------+
| piplock         | Overwrite the Pipfile.lock in the source       |
|                 | with the generated version from the            |
|                 | application image                              |
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

