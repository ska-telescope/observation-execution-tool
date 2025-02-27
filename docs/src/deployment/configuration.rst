.. _configuration:

Configuration
======================

The following environment variables are used to configure the application. They are set via a Kubernetes ConfigMap
with values coming from the Helm values.yaml. See :doc:`deployment_to_kubernetes`

Generally, if an variable default can be set in the application it will be. There are then also some defaults in the Helm values.
For more dynamic values that depend on the release name or namespace, the environment variables have a sensible default in the ConfigMap
but also can be overwritten via the values.yaml

.. note::
    There are some environment variables defined in the OET Helm chart that are not used directly by the OET application so are not listed here.
    As the OET executes scripts in child process that will be using the ska-oso-scripting library, environment variables expected by the library need to be defined in the OET process
    They are documented in the `RTD for ska-oso-scripting <https://developer.skao.int/projects/ska-oso-scripting/en/latest/?badge=latest>`_


.. list-table:: Environment variables used by ska-oso-oet
   :widths: 10 10 10 10 10
   :header-rows: 1

   * - Environment variable
     - Description
     - Required/optional in the application
     - Corresponding Helm value
     - Required/optional in the Helm chart
   * - SKUID_URL
     - The Kubernetes service address of a running SKUID service
     - Required
     - ``ska-oso-oet.rest.skuid.url``
     - - Optional - will fall back on: ``ska-ser-skuid-{{ .Release.Name }}-svc.{{ .Release.Namespace }}.svc.{{ .Values.global.cluster_domain }}:9870``
   * - ODA_BACKEND_TYPE
     - Defines whether the ODA interfaces should connect to a Postgresql instance or use the filesystem.
     - Optional - default: ``postgres``
     - ``ska-oso-oet.rest.oda.backendType``
     - Required - default set to ``postgres``
   * - ODA_DATA_DIR
     - The base filesystem location that the filesystem ODA will use to store and retrieve entities.
     - Optional - default: ``/var/lib/oda``
     - ``ska-oso-oet.rest.backend.type``
     - Required - default set to ``postgres``
   * - POSTGRES_HOST
     - The address of the PostgreSQL instance that the postgres ODA will connect to.
     - Required if ``ODA_BACKEND_TYPE`` is ``postgres``
     - ``ska-oso-oet.rest.oda.postgres.host``
     - Optional - will fall back on: ``{{ .Release.Name }}-postgresql.{{ .Release.Namespace }}.svc.{{ .Values.global.cluster_domain }}``

   * - ADMIN_POSTGRES_USER
     - The admin user of the PostgreSQL instance that the postgres ODA will connect to.
     - Optional - default: ``postgres``
     - ``ska-oso-oet.rest.oda.postgres.user``
     - Optional - no default in chart
   * - ADMIN_POSTGRES_PASSWORD
     - The admin password of the PostgreSQL instance that the postgres ODA will connect to.
     - Required if ``ODA_BACKEND_TYPE`` is ``postgres``
     - Pulled from Vault - see :doc:`secret_management`
     -
   * - POSTGRES_PORT
     - The port of the PostgreSQL instance that the postgres ODA will connect to.
     - Optional - default: ``5432``
     - ``ska-oso-oet.rest.oda.postgres.port``
     - Optional - no default in chart
   * - POSTGRES_DB_NAME
     - The name of the database within a PostgreSQL instance that the postgres ODA will connect to.
     - Optional - default: ``postgres``
     - ``ska-oso-oet.rest.oda.postgres.db.name``
     - Optional - no default in chart