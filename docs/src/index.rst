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

This project contains the code for the Observation Execution Tool, the
application which provides high-level scripting facilities and a high-level
scripting UI for the SKA.

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
