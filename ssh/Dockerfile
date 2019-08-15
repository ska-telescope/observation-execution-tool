FROM nexus.engageska-portugal.pt/ska-telescope/oet:latest

USER root

ARG SSH_PASSWORD=oet

ENV ssh_cmd tango:$SSH_PASSWORD

RUN echo $ssh_cmd

RUN apt-get update && apt-get install -y \
  openssh-server \
  && rm -rf /var/lib/apt/lists/*

RUN mkdir /var/run/sshd
RUN echo $ssh_cmd | chpasswd

# Allows the SSH user to pass environment variables into their SSH session
# For this stage of development this is useful as it allows the TANGO_HOST
# to be overwritten by the user.
RUN echo "PermitUserEnvironment yes" >> /etc/ssh/sshd_config

# Setup the profile so that the OET iTango CLI is started
# when the user connects
RUN echo "cd /app" >> /home/tango/.bashrc
RUN echo "/venv/bin/itango3 --profile=ska" >> /home/tango/.bashrc

# SSH login fix. Otherwise user is kicked off after login
RUN sed 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' -i /etc/pam.d/sshd

ENV NOTVISIBLE "in users profile"
RUN echo "export VISIBLE=now" >> /etc/profile

EXPOSE 22
CMD ["/usr/sbin/sshd", "-D"]