FROM nexus.engageska-portugal.pt/ska-docker/ska-python-buildenv:latest AS buildenv
FROM nexus.engageska-portugal.pt/ska-docker/ska-python-runtime:latest AS runtime

# copy the SKA profile that will handle initialising the OET domain objects and any other
# aspects of the configuration
RUN mkdir -p ~/.ipython/profile_ska
RUN cp -r /app/profile_ska ~/.ipython/

CMD ["/venv/bin/itango3","--profile=ska"]
