Observation Execution Tool
==========================

This project contains the code for the Observation Execution Tool, the
application which provides high-level scripting facilities and a high-level
scripting UI for the SKA.

To clone this repository, run

```
git clone --recurse-submodules git@gitlab.com:ska-telescope/ska-oso-oet.git
```

To refresh the GitLab Submodule, execute below commands:

```
git submodule update --recursive --remote
git submodule update --init --recursive
```

## Build and test

Execute the test suite and lint the project with:

```
make python-test
make python-lint
```

To build a new Docker image for the OET, run

```
make oci-build
```

To rebuild the PlantUML and drawio diagrams after modification, from a
non-interactive session run

```
make diagrams
```

[![Documentation Status](https://readthedocs.org/projects/ska-telescope-ska-oso-oet/badge/?version=latest)](https://developer.skao.int/projects/ska-oso-oet/en/latest/?badge=latest)

Documentation can be found in the ``docs`` folder.
