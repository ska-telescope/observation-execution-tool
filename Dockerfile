ARG BUILD_IMAGE="artefact.skao.int/ska-tango-images-pytango-builder:9.3.14"
ARG BASE_IMAGE="artefact.skao.int/ska-tango-images-pytango-runtime:9.3.14"
ARG CAR_OCI_REGISTRY_HOST=artefact.skao.int

FROM $BUILD_IMAGE AS buildenv
FROM $BASE_IMAGE

ARG CAR_PYPI_REPOSITORY_URL=https://artefact.skao.int/repository/pypi-internal
ENV PIP_INDEX_URL ${CAR_PYPI_REPOSITORY_URL}/simple

# Install Poetry
USER root
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | POETRY_HOME=/opt/poetry python - && \
    cd /usr/local/bin && \
    chmod a+x /opt/poetry/bin/poetry && \
    ln -s /opt/poetry/bin/poetry && \
    poetry config virtualenvs.create false

RUN apt-get update && apt-get -y install git
# Copy poetry.lock* in case it doesn't exist in the repo
COPY pyproject.toml poetry.lock* ./

# Install runtime dependencies and the app
RUN poetry install --no-dev

USER tango
RUN poetry config virtualenvs.create false

CMD ["python3", "-m", "ska_oso_oet.procedure.application.main"]
