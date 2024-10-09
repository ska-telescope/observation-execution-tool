.. _persistent_environments:

Persistent Environments
=========================

Similar to other applications, there are several deployments of the application via CICD pipelines.

Integration
------------

The integration environment deploys the **latest main branch version** of the application, and is triggered by every
commit to the main branch. It should always be available at

https://k8s.stfc.skao.int/integration-ska-oso-oet/oet/api/v6/ui/

Staging
--------

The staging environment deploys the **latest released version** of the application and pulls the version from CAR. It should always be available at

https://k8s.stfc.skao.int/staging-ska-oso-oet/oet/api/v6/ui/

ska-oso-integration
---------------------

`ska-oso-integration <https://developer.skao.int/projects/ska-oso-integration/en/latest/?badge=latest>`_ is a separate environment
deployed by its own pipeline for stable, released versions of OSO services that are integrated with the other OSO applications.

See the linked RTD for the URL for the OET in that environment.

