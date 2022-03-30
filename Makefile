#
# CAR_OCI_REGISTRY_HOST, CAR_OCI_REGISTRY_USERNAME and PROJECT are combined to define
# the Docker tag for this project. The definition below inherits the standard
# value for CAR_OCI_REGISTRY_HOST (=artefact.skao.int) and overwrites
# CAR_OCI_REGISTRY_USERNAME and PROJECT to give a final Docker tag of
# artefact.skao.int/ska-tango-examples/powersupply
#
CAR_OCI_REGISTRY_HOST ?= artefact.skao.int
CAR_OCI_REGISTRY_USERNAME ?= ska-telescope
PROJECT_NAME = ska-oso-oet

# include makefile to pick up the standard Make targets from the submodule
-include .make/base.mk
-include .make/python.mk
-include .make/oci.mk
-include .make/k8s.mk
-include .make/helm.mk

# include your own private variables for custom deployment configuration
-include PrivateRules.mak

IMAGE_TO_TEST = $(CAR_OCI_REGISTRY_HOST)/$(strip $(OCI_IMAGE)):$(VERSION)

# Set python-test make target to run unit tests and not the integration tests
PYTHON_TEST_FILE = tests/unit/

K8S_CHART = ska-oso-oet-umbrella

# unset defaults so settings in pyproject.toml take effect
PYTHON_SWITCHES_FOR_BLACK =
PYTHON_SWITCHES_FOR_ISORT =

# Disable warning, convention, and refactoring messages
# Disable errors:
PYTHON_SWITCHES_FOR_PYLINT = --disable=C,R


up: namespace install-chart wait

dev-up: K8S_CHART_PARAMS = --set ska-oso-oet.rest.image.tag=$(VERSION) --set ska-oso-oet.rest.ingress.enabled=true
dev-up: k8s-namespace k8s-install-chart k8s-wait ## bring up developer deployment

dev-down: k8s-uninstall-chart k8s-delete-namespace  ## tear down developer deployment

rest:  ## start OET REST server
	docker run --rm -p 5000:5000 -v $(CURDIR):/app -e PYTHONPATH=/app/src -w /app --name=ska-oso-oet-rest $(IMAGE_TO_TEST) python -m ska_oso_oet.procedure.application.main

diagrams:  ## recreate PlantUML diagrams whose source has been modified
	@for i in $$(git diff --name-only -- '*.puml'); \
	do \
		echo "Recreating $${i%%.*}.png"; \
		cat $$i | docker run --rm think/plantuml -tsvg $$i > $${i%%.*}.svg; \
	done
	docker run -v $(CURDIR):/data rlespinasse/drawio-export --format=svg --on-changes --remove-page-suffix docs/src/diagrams

k8s-pre-test:
	kubectl cp tests/acceptance/ska_oso_oet/scripts/ $(KUBE_NAMESPACE)/ska-oso-oet-rest-$(HELM_RELEASE)-0:/tmp/scripts

k8s-post-test:
	kubectl -n $(KUBE_NAMESPACE) exec ska-oso-oet-rest-$(HELM_RELEASE)-0 -- rm -r /tmp/scripts