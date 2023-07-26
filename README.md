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
helm plugin install https://github.com/helm-unittest/helm-unittest.git
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

## OpenAPI Implementation
The OpenAPI Specification (OAS) defines a standard, language-agnostic interface to HTTP APIs which allows both humans and computers to discover and understand the capabilities of the service without access to source code, documentation, or through network traffic inspection.

Version used: 3.0.0

[OpenAPI Specification User Guide](https://spec.openapis.org/oas/v3.0.0)

For accessing Swagger UI on local development environment follow below steps:

Pre-requisite:
- Run ODA Application server : [Refer this ODA Installation link](https://gitlab.com/ska-telescope/db/ska-db-oda/-/blob/main/README.md?ref_type=heads) 

- Export ODA Server URL as an Environment variable ODA_URI
```
export ODA_URI=<oda_server_url>
```

- Start the OET REST API server:
```
python src/ska_oso_oet/main.py
```

- Access Swagger UI On a browser using below link:
```
http://{hostname}:{port}/api/v1.0/ui
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


