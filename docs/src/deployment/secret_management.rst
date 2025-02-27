.. _secret_management:

Secret Management
=========================

``ska-oso-oet`` requires secret values to connect to the ODA PostgreSQL instance.

The deployment is configured to set the ``ADMIN_POSTGRES_PASSWORD`` environment variable from the Kubernetes
Secret that is the password to the PostgreSQL isntance that the ``ska-db-oda-umbrella`` chart deploys.

To use a different Secret, the ``.Values.rest.oda.postgres.password.secret`` value can be overwritten with the Kubernetes Secret
resource name and the ``.Values.rest.oda.postgres.password.key`` with the key within that Secret.

