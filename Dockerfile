FROM nexus.engageska-portugal.pt/ska-docker/ska-python-buildenv:9.3.3.1 AS buildenv
FROM nexus.engageska-portugal.pt/ska-docker/ska-python-runtime:9.3.3.1 AS runtime

ENV PATH="/home/tango/.local/bin:${PATH}"
RUN python3 -m pip install \
    --extra-index-url https://nexus.engageska-portugal.pt/repository/pypi/simple \
    # Running tests via an IDE required the test dependencies to be installed.
    # The quickest way to achieve this is by uncommenting the line below
    # -r tests/requirements.txt \
    .

CMD ["python3", "-m", "oet.procedure.application.main"]
