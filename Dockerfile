ARG BUILD_IMAGE="artefact.skao.int/ska-tango-images-pytango-builder:9.3.28"
ARG BASE_IMAGE="artefact.skao.int/ska-tango-images-pytango-runtime:9.3.16"
ARG CAR_OCI_REGISTRY_HOST=artefact.skao.int

FROM $BUILD_IMAGE AS buildenv
FROM $BASE_IMAGE

ARG CAR_PYPI_REPOSITORY_URL=https://artefact.skao.int/repository/pypi-internal
ENV PIP_INDEX_URL ${CAR_PYPI_REPOSITORY_URL}/simple

USER root

RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get -y install --no-install-recommends git python3-venv && \
    rm -rf /var/lib/apt/lists/*

# Copy poetry.lock* in case it doesn't exist in the repo
COPY pyproject.toml poetry.lock* ./

# Install runtime dependencies. Add --dev to export for images usable in an IDE
# Note that the 'pip install .' MUST be present otherwise a potentially stale version
# of ska-oso-oet could be installed system-wide as a dependency of ska-oso-scripting
RUN poetry export --format requirements.txt --output poetry-requirements.txt --without-hashes && \
    pip install -r poetry-requirements.txt && \
    rm poetry-requirements.txt && \
    pip install .

# clone the ska-oso-scripting library
RUN git clone -b master https://gitlab.com/ska-telescope/oso/ska-oso-scripting.git /repos/scripting/

# install ska-oso-scripting library to provide a default environment and set of
# default control scripts. This is done as root so that the default environment
# is installed to system dist-packages.
RUN python3 -m pip install \
    --extra-index-url=https://artefact.skao.int/repository/pypi-all/simple ska-oso-scripting==4.5.0

# link default script location to a shorter path to make CLI interactions easier
RUN ln -s /usr/local/lib/python3.7/dist-packages/scripts /scripts

USER tango
RUN poetry config virtualenvs.create false

CMD ["python3", "-m", "ska_oso_oet.procedure.application.main"]