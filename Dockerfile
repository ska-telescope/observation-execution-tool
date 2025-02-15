ARG BUILD_IMAGE="artefact.skao.int/ska-cicd-k8s-tools-build-deploy:0.12.0"
ARG BASE_IMAGE="artefact.skao.int/ska-cicd-k8s-tools-build-deploy:0.12.0"

FROM $BUILD_IMAGE AS buildenv
FROM $BASE_IMAGE AS runtime

ENV APP_USER="tango"
ENV APP_DIR="/app"

ARG CAR_PYPI_REPOSITORY_URL=https://artefact.skao.int/repository/pypi-internal
ARG SCRIPTS_LOCATION=/scripts
ENV PIP_INDEX_URL ${CAR_PYPI_REPOSITORY_URL}/simple

USER root

RUN adduser $APP_USER --disabled-password --home $APP_DIR

WORKDIR $APP_DIR

ENV PATH="$PATH:$APP_DIR/.local/bin"

RUN pip install 'poetry<2.0.0' poetry-plugin-export && \
    poetry config warnings.export false


RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get -y install --no-install-recommends git python3-venv && \
    rm -rf /var/lib/apt/lists/*

# Used by the FilesystemRepository implementation of the ODA
RUN mkdir -p /var/lib/oda && chown -R ${APP_USER} /var/lib/oda

# install ska-oso-scripting library to provide a default environment and set of
# default control scripts. This is done as root so that the default environment
# is installed to system dist-packages.
RUN python3 -m pip install \
    --extra-index-url=https://artefact.skao.int/repository/pypi-internal/simple ska-oso-scripting==10.4.0

COPY --chown=$APP_USER:$APP_USER . .

# Install runtime dependencies. Add --dev to export for images usable in an IDE
# Note that the 'pip install .' MUST be present otherwise a potentially stale version
# of ska-oso-oet could be installed system-wide as a dependency of ska-oso-scripting
RUN poetry export --format requirements.txt --output poetry-requirements.txt --without-hashes && \
    pip install -r poetry-requirements.txt && \
    rm poetry-requirements.txt && \
    pip install .

## To build OET with an unreleased version of scripting for testing purposes, use the following
#RUN python3 -m pip install  \
#    --extra-index-url=https://artefact.skao.int/repository/pypi-all/simple  \
#    --index-url https://${GITLAB_PRIVATE_TOKEN}gitlab.com/api/v4/projects/22057734/packages/pypi/simple \
#    ska-oso-scripting==6.1.0+dev.c580f9d62

# install the client into the image so it can be used in the default k8s installation
RUN pip install ska-oso-oet-client==1.1.0

# link default script location to a shorter path to make CLI interactions easier
RUN ln -s /usr/local/lib/python3.10/dist-packages/scripts $SCRIPTS_LOCATION

# Create the location for the Activity domain to store SBs
RUN mkdir -p /tmp/sbs && chown -R ${APP_USER} /tmp/sbs

USER ${APP_USER}

# give developers access to Pytango in site-packages for when updating poetry.locl
RUN poetry config virtualenvs.options.system-site-packages true

CMD ["python3", "-m", "ska_oso_oet.procedure.application.main"]
