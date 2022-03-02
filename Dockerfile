ARG CAR_OCI_REGISTRY_HOST=artefact.skao.int

FROM $CAR_OCI_REGISTRY_HOST/ska-tango-images-pytango-builder:9.3.10 AS buildenv
FROM $CAR_OCI_REGISTRY_HOST/ska-tango-images-pytango-runtime:9.3.10 AS runtime

ARG CAR_PYPI_REPOSITORY_URL=https://artefact.skao.int/repository/pypi-internal
ENV PIP_INDEX_URL ${CAR_PYPI_REPOSITORY_URL}/simple

ENV PATH="/home/tango/.local/bin:${PATH}"
RUN --mount=type=cache,target=/home/tango/.cache/pip,uid=1000,gid=1000 python3 -m pip install \
#RUN python3 -m pip install \
    --use-feature=in-tree-build \
    # Running tests via an IDE required the test dependencies to be installed.
    # The quickest way to achieve this is by uncommenting the line below
    -r tests/requirements.txt \
    .

CMD ["python3", "-m", "ska_oso_oet.procedure.application.main"]
