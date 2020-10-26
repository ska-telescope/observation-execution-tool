FROM nexus.engageska-portugal.pt/ska-docker/ska-python-buildenv:9.3.2.1 AS buildenv
FROM nexus.engageska-portugal.pt/ska-docker/ska-python-runtime:9.3.2.1 AS runtime

# copy the SKA profile that will handle initialising the OET domain objects and any other
# aspects of the configuration
RUN mkdir -p ~/.ipython/profile_ska
RUN cp -r /app/profile_ska ~/.ipython/

ENV PATH="/home/tango/.local/bin:${PATH}"
RUN python3 -m pip install --extra-index-url https://nexus.engageska-portugal.pt/repository/pypi/simple -rrequirements.txt .

CMD ["python3","/app/oet/procedure/application/main.py"]
