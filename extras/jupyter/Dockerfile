FROM nexus.engageska-portugal.pt/ska-telescope/observation-execution-tool:latest

# Add Tini. Tini operates as a process subreaper for jupyter. This prevents
# kernel crashes.
ENV TINI_VERSION v0.6.0

USER root
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /usr/bin/tini
RUN chmod +x /usr/bin/tini
RUN usermod -s /bin/bash tango

USER tango
ENV PATH="/home/tango/.local/bin:${PATH}"
RUN python3 -m pip install jupyter
RUN jupyter notebook --generate-config
RUN python3 -m itango.install

# disable authentication
RUN echo "c.NotebookApp.token = ''" >> /home/tango/.jupyter/jupyter_notebook_config.py

# enable terminals
RUN echo "c.NotebookApp.terminals_enabled = True" >> /home/tango/.jupyter/jupyter_notebook_config.py

EXPOSE 8888
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["jupyter", "notebook", "--ip=0.0.0.0", "--no-browser", "--port=8888"]