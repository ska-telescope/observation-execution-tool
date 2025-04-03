.. _architecture_module_rest_api:

*********************
Module View: REST API
*********************

The OET REST API presents REST resources for the Activity and Procedure domain.
While it is expected that the OET will be used via the UI or CLI, the API can be used to
manage the lifecycle of SBDefinitions or Python scripts running on a remote
server and to inspect their status.

The SwaggerUI for the integration deployment is available at https://k8s.stfc.skao.int/integration-ska-oso-oet/oet/api/v7/ui/

and the OpenAPI json at https://k8s.stfc.skao.int/integration-ska-oso-oet/oet/api/v7/openapi.json

These document the API resources along with their request and response bodies. The SwaggerUI can be used
to send requests and includes example payloads.
