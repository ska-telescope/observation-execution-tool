ARG CAR_OCI_REGISTRY_HOST

FROM $CAR_OCI_REGISTRY_HOST/ska-tango-images-pytango-builder:9.3.10 AS buildenv
FROM $CAR_OCI_REGISTRY_HOST/ska-tango-images-pytango-runtime:9.3.10 AS runtime

ARG CAR_PYPI_REPOSITORY_URL
ENV PIP_INDEX_URL ${CAR_PYPI_REPOSITORY_URL}/simple

ENV PATH="/home/tango/.local/bin:${PATH}"
RUN python3 -m pip install \
    --use-feature=in-tree-build \
    # Running tests via an IDE required the test dependencies to be installed.
    # The quickest way to achieve this is by uncommenting the line below
    # -r tests/requirements.txt \
    .

CMD ["python3", "-m", "oet.procedure.application.main"]
