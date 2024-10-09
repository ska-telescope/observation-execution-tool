SKA OSO Observation Execution Tool
==================================

The ska-oso-oet project contains the code for the Observation Execution Tool (OET),
the application which provides on-demand Python script execution for the SKA. When
SBDs are sent for execution, they will contain a reference to the script that should
be used to execute it.

For an overview of the applications and functionality within OSO, see `Solution Intent <https://confluence.skatelescope.org/pages/viewpage.action?pageId=159387040>`_.

For information on deploying and configuring the application in a given Kubernetes or local environment, see the 'Deploying and configuring' section.

For user information for a deployed instance of this application, see the 'User Guide'.

For developer information, application internals, and information about interactions with other OSO applications, see the 'Application internals and developer information' section

For instructions on developing the application, see the `README <https://gitlab.com/ska-telescope/oso/ska-oso-oet/-/blob/main/README.md>`_

.. toctree::
    :maxdepth: 1
    :caption: Releases
    :hidden:

    CHANGELOG.rst


.. toctree::
    :maxdepth: 2
    :caption: General
    :hidden:

    general/background.rst


.. toctree::
    :maxdepth: 2
    :caption: Deploying and configuring
    :hidden:

    deployment/quickstart.rst
    deployment/environment_variables.rst
    deployment/deployment_to_kubernetes.rst
    deployment/persistent_environments.rst

.. toctree::
    :maxdepth: 2
    :caption: User Guide
    :hidden:

    external/cli.rst


.. toctree::
    :maxdepth: 2
    :caption: Application internals and developer information
    :hidden:

    internal/architecture/architecture_backend_candc.rst
    internal/architecture/architecture_backend_module_activity_ui.rst
    internal/architecture/architecture_backend_module_execution.rst
    internal/architecture/architecture_backend_module_script_exec_ui.rst
    internal/architecture/architecture_module_rest_api.rst
    internal/api_public/index.rst
    internal/api_private/index.rst
