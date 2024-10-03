Quickstart
==========
Build a new OET image:

::

  make oci-build

Execute the test suite and lint the project with:

::

  make python-test
  make python-lint

Format and lint on commit
-------------------------

We recommend you use `pre-commit <https://pre-commit.com>`_ to automatically
format and lint your commits. The commands below should be enough to get you
up and running. Reference the official `documentation <https://pre-commit.com/#install>`_
for full installation details.

*Pre-commit installation on Linux*

.. code-block:: shell

    # install pre-commit
    sudo pip3 install pre-commit

    # install git hook scripts
    pre-commit install

    # uninstall git hook scripts
    pre-commit uninstall


*Pre-commit installation on MacOS*

The commands below were tested on MacOS 10.15.

.. code-block:: shell

    # install pre-commit
    pip3 install --user pre-commit

    # install git hook scripts
    ~/Library/Python/3.8/bin/pre-commit install

    # uninstall git hook scripts
    ~/Library/Python/3.8/bin/pre-commit uninstall

Makefile targets
----------------
This project extends the standard SKA Make targets with a few additional Make
targets that can be useful for developers. These targets are:

+-----------------+------------------------------------------------+
| Makefile target | Description                                    |
+=================+================================================+
| dev-up          | deploy the OET using the current developer     |
|                 | image, exposing REST ingress on the host       |
+-----------------+------------------------------------------------+
| dev-down        | tear down the developer OET deployment         |
+-----------------+------------------------------------------------+
| rest            | start the OET backend in a Docker container    |
+-----------------+------------------------------------------------+
| diagrams        | recreate PlantUML diagrams whose source has    |
|                 | been modified                                  |
+-----------------+------------------------------------------------+
| k8s-chart-test  | run helm chart unit tests                      |
|                 | (note: requires helm unittest plugin:          |
|                 | https://github.com/quintush/helm-unittest )    |
+-----------------+------------------------------------------------+
| help            | show a summary of the makefile targets above   |
+-----------------+------------------------------------------------+

Local development with k8s
--------------------------
OET REST server can be deployed locally using Helm and Kubernetes and OET CLI
:doc:`../external/cli` can be used to communicate with the server. OET CLI is
installed as part of the Poetry virtual environment (see README) or can be
used inside a running OET container/pod.

If using OET CLI within Poetry virtual environment these steps are needed
for the CLI to access the REST server:

- set `rest.ingress.enabled` to `true` in `charts/ska-oso-oet/values.yaml`
- set `OET_URL` environment variable with `export OET_URL=http://<minikube IP>/<kube namespace>/oet/api/v<OET major version>`

To deploy OET REST server run

::

   make k8s-chart-install && make k8s-wait



Feature flags
-------------
OET feature flags are configured via environment variables and configuration
files. The configuration file, ska_oso_oet.ini, can be located either in the user's
home directory, or the root of the installation folder.

Feature flags are read in this order:

#. environment variable;
#. ska_oso_oet.ini configuration file;
#. default flag value as specified in OET code.

No feature flags are available at this time.
