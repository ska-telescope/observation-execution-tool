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

# Build and test

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

To access the Swagger UI for a Kubernetes deployment, follow the instructions above then the UI should be available at `http://<KUBE_HOST>/<KUBE_NAMESPACE>/ska-oso-oet/ui/`

For accessing Swagger UI on local development environment follow below steps:

Pre-requisite:
- Run ODA Application server : [Refer this ODA Installation link](https://gitlab.com/ska-telescope/db/ska-db-oda/-/blob/main/README.md?ref_type=heads) 

- Export ODA Server URL as an Environment variable ODA_URL
```
export ODA_URL=<oda_server_url>
```

- Start the OET REST API server:
```
python src/ska_oso_oet/main.py
```

- Access Swagger UI On a browser using below link:
```
http://{hostname}:{port}/ska-oso-oet/oet/api/v<OET major version>/ui
```


# Deployments from CICD

## Deploying to non-production environments

There are 3 different environments which are defined through the standard pipeline templates. They need to be manually triggered in the Gitlab UI.

1. `dev` - a temporary (4 hours) deployment from a feature branch, using the artefacts built in the branch pipeline
2. `integration` - a permanent deployment from the main branch, using the latest version of the artefacts built in the main pipeline
3. `staging` - a permanent deployment of the latest published artefact from CAR

To find the URL for the environment, see the 'info' job of the CICD pipeline stage, which should output the URL alongside the status of the Kubernetes pods.
Generally the API URL should be available at  `https://k8s.stfc.skao.int/$KUBE_NAMESPACE/ska-oso-oet/api/`

# Documentation

[![Documentation Status](https://readthedocs.org/projects/ska-telescope-ska-oso-oet/badge/?version=latest)](https://developer.skao.int/projects/ska-oso-oet/en/latest/?badge=latest)

To build the html version of the documentation, start from the root directory and first install the dependency using 
``poetry install --only docs`` and then type ``make docs-build html``. Read the documentation by pointing your browser
at ``docs/build/html/index.html``.
