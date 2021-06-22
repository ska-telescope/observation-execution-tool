# Contributing to OET

:+1::tada: Thank you for taking the time to contribute! :tada::+1:

The following is a set of guidelines for contributing to the SKA Observation
Execution Tool and its packages, which are hosted in the
[oet](https://gitlab.com/ska-telescope/ska-oso-oet) project on
GitLab. These are mostly guidelines, not rules. Use your best judgment, and
feel free to propose changes to this document in a merge request.

#### Table of Contents

[Code of Conduct](#code-of-conduct)

[I don't want to read this whole thing, I just have a question!!!](#i-dont-want-to-read-this-whole-thing-i-just-have-a-question)

[How Can I Contribute?](#how-can-i-contribute)
  * [Local Development](#local-development)
  * [Merge Requests](#merge-requests)

[Styleguides](#styleguides)
  * [Git Commit Messages](#git-commit-messages)
  * [Python Styleguide](#python-styleguide)

## Code of Conduct

This project and everyone participating in it is governed by the
[SKA Code of Conduct](https://developer.skatelescope.org/en/latest/policies/code-of-conduct.html).
By participating, you are expected to uphold this code. Please report
unacceptable behavior.

## I don't want to read this whole thing I just have a question!!!

> **Note:** Please don't file an issue to ask a question. You'll get faster
> results by using the resources below.

You can ask your question directly to the developers on the SKA Telescope Slack team:

* [Join the SKAO Slack Team](https://skasoftware.slack.com/)
    * Even though Slack is a chat service, sometimes it takes several hours
      for community members to respond &mdash; please be patient!
    * Use the `#proj-oet` channel for support, questions, and discussion about
      writing or contributing to OET packages.
    * As a last resort, Use the `#team-buttons` channel to contact developers
      directly.
    * There are many other channels available, check the channel list.

## How Can I Contribute?

### Local development

OET and all packages can be developed locally. For instructions on how to do
this, see the [OET Quickstart](https://developer.skatelescope.org/projects/observation-execution-tool/en/latest/index.html)
section on the SKA developer portal.

### Merge Requests

The process described here has several goals:

- Maintain OET's quality
- Fix problems that are important to users
- Enable a sustainable system for OET maintainers to review contributions

Please follow these steps to have your contribution considered by the maintainers:

1. Follow the [styleguides](#styleguides)
2. After you submit your merge request, verify that your [CI pipeline](https://gitlab.com/ska-telescope/ska-oso-oet/-/pipelines)
   tests are passing
   <details><summary>What if the CI pipelines are failing?</summary>If a
   CI pipeline is failing, and you believe that the failure is unrelated to
   your change, please leave a comment on the merge request explaining why you
   believe the failure is unrelated. A maintainer will re-run the status check
   for you. If we conclude that the failure was a false positive, then we will
   open an issue to track that problem with our CI suite.</details>

While the prerequisites above must be satisfied prior to having your merge
request reviewed, the reviewer(s) may ask you to complete additional design
work, tests, or other changes before your merge request can be ultimately
accepted.

## Styleguides

### Git Commit Messages

* Use the present tense ("Add feature" not "Added feature")
* Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
* Limit the first line to 72 characters or less
* Reference issues and merge requests liberally after the first line

### Python styleguide

All Python code is formatted with [Black](https://github.com/psf/black)
and linted using [flake-8](https://flake8.pycqa.org/en/latest/).

#### Format and lint on commit

We recommend you use [pre-commit](https://pre-commit.com) to automatically
format and lint your commits. The commands below should be enough to get you
up and running. Reference the official [documentation](https://pre-commit.com/#install)
for full installation details.

##### Pre-commit installation on Linux

```shell
# install pre-commit
sudo pip3 install pre-commit

# install git hook scripts
pre-commit install

# uninstall git hook scripts
# pre-commit uninstall
```

##### Pre-commit installation on MacOS

The commands below were tested on MacOS 10.15.

```shell
# install pre-commit
pip3 install --user pre-commit

# install git hook scripts
~/Library/Python/3.8/bin/pre-commit install

# uninstall git hook scripts
# ~/Library/Python/3.8/bin/pre-commit uninstall
```
