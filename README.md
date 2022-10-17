Observation Execution Tool
==========================

This project contains the code for the Observation Execution Tool, the
application which provides high-level scripting facilities and a high-level
scripting UI for the SKA.

To clone this repository, run

```
git clone --recurse-submodules git@gitlab.com:ska-telescope/oso/ska-oso-oet.git
```

To refresh the GitLab Submodule, execute below commands:

```
git submodule update --recursive --remote
git submodule update --init --recursive
```

## Build and test

Install dependencies with Poetry and activate the virtual environment

```
poetry install
poetry shell
```

To build a new Docker image for the OET, run

```
make oci-build
```

Execute the test suite and lint the project with:

```
make python-test
make python-lint
```

To run a helm chart unit tests to verify helm chart configuration:
 
```
helm plugin install https://github.com/quintush/helm-unittest
make k8s-chart-test
```

Execute the BDD acceptance tests in k8s environment with:

```
make k8s-install-chart && make k8s-wait
make k8s-test
make k8s-uninstall-chart
```

The umbrella Helm chart also deploys the ska-db-oda service and related Postgres instance by default. This is
used in the BDD tests to test the full integration from the OET to Postgres. For a lightweight deployment of the OET,
which uses the filesystem implementation of the ODA, run

```
make dev-up
```

To rebuild the PlantUML and drawio diagrams after modification, from a
non-interactive session run

```
make diagrams
```

## Documentation

[![Documentation Status](https://readthedocs.org/projects/ska-telescope-ska-oso-oet/badge/?version=latest)](https://developer.skao.int/projects/ska-oso-oet/en/latest/?badge=latest)

Documentation can be found in the ``docs`` folder. To build docs, install the 
documentation specific requirements:

```
pip3 install sphinx sphinx-rtd-theme recommonmark
```

and build the documentation (will be built in docs/build folder) with 

```
make docs-build html
```