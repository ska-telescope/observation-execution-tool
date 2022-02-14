Observation Execution Tool
==========================

## Building steps

This project contains the code for the Observation Execution Tool, the
application which provides high-level scripting facilities and a high-level
scripting UI for the SKA.

This project is structured to use Docker containers for development and
testing so that the build environment, test environment and test results are
all completely reproducible and are independent of host environment. It uses
``make`` to provide a consistent UI (full details can be found in the ```docs```).

Build a new Docker image for the OET with:

```
make build
```

Execute the test suite and lint the project with:

```
make test
make lint
```

Launch an interactive shell inside a container, with your workspace visible
inside the container:

```
make interactive
```

An interactive session can be useful for rebuilding the project documentation.
From an interactive session, run

```
cd docs
make html
# open build/html/index.html in browser to see regenerated docs
```

To rebuild the PlantUML and drawio diagrams after modification, from a
non-interactive session run

```
make diagrams
```

[![Documentation Status](https://readthedocs.org/projects/ska-telescope-ska-oso-oet/badge/?version=latest)](https://developer.skao.int/projects/ska-oso-oet/en/latest/?badge=latest)

Documentation can be found in the ``docs`` folder.
