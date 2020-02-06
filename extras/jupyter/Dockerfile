FROM nexus.engageska-portugal.pt/ska-telescope/oet:latest

# Add Tini. Tini operates as a process subreaper for jupyter. This prevents
# kernel crashes.
ENV TINI_VERSION v0.6.0
USER root
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /usr/bin/tini
RUN chmod +x /usr/bin/tini
USER tango

RUN /venv/bin/pip3 install jupyter

RUN /venv/bin/jupyter notebook --generate-config

# disable authentication
RUN echo "c.NotebookApp.token = ''" >> /home/tango/.jupyter/jupyter_notebook_config.py

# enable terminals
RUN echo "c.NotebookApp.terminals_enabled = True" >> /home/tango/.jupyter/jupyter_notebook_config.py

EXPOSE 8888
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/venv/bin/jupyter", "notebook", "--ip=0.0.0.0", "--no-browser", "--port=8888"]