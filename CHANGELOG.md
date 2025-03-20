Changelog
==========

All notable changes to this project will be documented in this file.
This project adheres to [Semantic Versioning](http://semver.org/).

Unreleased
**********
* Updating to use Pydantic BaseModels throughout the OET

6.6.0
**********
* Update the Helm charts so that they have better defaults and require minimal changes in the makefile. See the docs
  Deployment > Configuration page.
* Pull the ODA password from a k8s secret
* Update to ODA v7.3.0

6.5.0
*****
* Updated Dockerfile to use poetry<2.0.0
* Removed `tango` module and `pytango` dependency
* Removed scan ID generators and scan ID management from OET's `procedure` module
* Removed cloned oso-scripting repo from OET Dockerfile
* Updated ska-oso-scripting to version 11.0.0 for OET default environment
* Added ska-oso-scripting dependency to `pyproject.toml` instead of installing it in `Dockerfile`
* Changed the `abort.py` script to be pulled from `ska-oso-scripting` instead of containing a local copy
* Added `SCRIPTS_LOCATION` environment variable for configuring location where static scripts are located
* Updated to ODA v7.2.0, which updated the PDM dependency to 17.1.2
* Removed `user`, `scan` and `subarray` topics as they are now part of oso-scripting
* Updated `ska-oso-oet-client` to patch v.1.1.2

6.4.1
******
* Updated OET values.yaml and ConfigMap to include `VALIDATION_STRICTNESS` to manage OSD validation strictness


6.4.0
******
* Update to use ODA v7.1.0

6.3.3
*****
* Bump ODA minor version and scripting version in the dockerfile. Fixes the simpleeval dependency issue and is a temp fix for the issue where the PDM version from the site packages is used. 
  It is a temp fix as it just brings the PDM versions in line, rather than fixing the underlying issue. 

6.3.2
*****

* Properly fix issue where default image tag was not set to the chart version in the Helm chart

6.3.1
*****

* Fix issue where default image tag was not set to the chart version in the Helm chart

6.3.0
*****

* Updates OET to use RESTless ODA (v6.0.0)

6.2.0
*****

* Updates OET to use PyTango 9.5, ODA v5.0.1 and, indirectly, PDM v14.3.0.


6.1.0
*****

* Updates OET to use ODA v3.0.0 and PDM v12.0.1
* Exposes SKUID URL via ska-oso-oet.rest.skuid.url Helm variable 
