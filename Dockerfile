ARG BUILD_IMAGE="artefact.skao.int/ska-cicd-k8s-tools-build-deploy:0.12.0"
ARG BASE_IMAGE="artefact.skao.int/ska-cicd-k8s-tools-build-deploy:0.12.0"

FROM $BUILD_IMAGE AS buildenv
FROM $BASE_IMAGE AS runtime

ENV APP_USER="tango"
ENV APP_DIR="/app"

ARG CAR_PYPI_REPOSITORY_URL=https://artefact.skao.int/repository/pypi-internal
ARG SCRIPTS_LOCATION=/scripts
ENV PIP_INDEX_URL=${CAR_PYPI_REPOSITORY_URL}/simple

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

COPY --chown=$APP_USER:$APP_USER . .

# Install runtime dependencies. Add --dev to export for images usable in an IDE
RUN poetry export --format requirements.txt --output poetry-requirements.txt --without-hashes && \
    pip install -r poetry-requirements.txt && \
    rm poetry-requirements.txt && \
    pip install .

# install the client into the image so it can be used in the default k8s installation
RUN pip install ska-oso-oet-client==1.2.1

# link default script location to a shorter path to make CLI interactions easier
RUN ln -s /usr/local/lib/python3.10/dist-packages/scripts $SCRIPTS_LOCATION

# Create the location for the Activity domain to store SBs
RUN mkdir -p /tmp/sbs && chown -R ${APP_USER} /tmp/sbs

USER ${APP_USER}

# give developers access to Pytango in site-packages for when updating poetry.locl
RUN poetry config virtualenvs.options.system-site-packages true

CMD ["python3", "-m", "ska_oso_oet.procedure.application.main"]
