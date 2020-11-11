FROM nexus.engageska-portugal.pt/ska-docker/ska-python-buildenv:9.3.2.1 AS buildenv
FROM nexus.engageska-portugal.pt/ska-docker/ska-python-runtime:9.3.2.1 AS runtime

ENV PATH="/home/tango/.local/bin:${PATH}"
RUN python3 -m pip install --extra-index-url https://nexus.engageska-portugal.pt/repository/pypi/simple -rrequirements.txt .

CMD ["python3","/app/oet/procedure/application/main.py"]
