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
RELEASE_NAME ?= test

# include makefile to pick up the standard Make targets from the submodule
-include .make/base.mk
-include .make/python.mk
-include .make/oci.mk
-include .make/k8s.mk
-include .make/helm.mk

# include your own private variables for custom deployment configuration
-include PrivateRules.mak

IMAGE_TO_TEST = $(CAR_OCI_REGISTRY_HOST)/$(strip $(OCI_IMAGE)):$(VERSION)

# The default ODA_URI points to the umbrella chart ODA deployment where data is
# lost on chart teardown. For longer-term data persistence, override ODA_URI to
# point to the persistent ODA deployment.
ODA_URI ?= http://ska-db-oda-rest-$(RELEASE_NAME):5000/$(KUBE_NAMESPACE)/api/v1

POSTGRES_HOST ?= $(RELEASE_NAME)-postgresql

K8S_CHART_PARAMS = \
  --set ska-oso-oet.rest.oda.url=$(ODA_URI) \
  --set ska-db-oda.rest.backend.type=filesystem \
  --set ska-db-oda.pgadmin4.enabled=false \
  --set ska-db-oda.postgresql.enabled=false
# Set postgres and pgadmin host if postgresql and/or pgadmin4 are enabled
#   --set ska-db-oda.rest.postgres.host=$(POSTGRES_HOST) \
#   --set ska-db-oda.pgadmin4.serverDefinitions.servers.firstServer.Host=$(POSTGRES_HOST) \

# If running in the CI pipeline, set the variables to point to the freshly
# built image in the GitLab registry
ifneq ($(CI_REGISTRY),)
K8S_CHART_PARAMS += --set ska-oso-oet.rest.image.tag=$(VERSION)-dev.c$(CI_COMMIT_SHORT_SHA) \
	--set ska-oso-oet.rest.image.registry=$(CI_REGISTRY)/ska-telescope/oso/ska-oso-oet
K8S_TEST_IMAGE_TO_TEST=$(CI_REGISTRY)/ska-telescope/oso/ska-oso-oet/ska-oso-oet:$(VERSION)-dev.c$(CI_COMMIT_SHORT_SHA)
endif

# Set the k8s test command run inside the testing pod to only run the acceptance
# tests (no k8s pod deployment required for unit tests)
K8S_TEST_TEST_COMMAND = ODA_URI=$(ODA_URI) KUBE_NAMESPACE=$(KUBE_NAMESPACE) pytest ./tests/acceptance | tee pytest.stdout

# Set python-test make target to run unit tests and not the integration tests
PYTHON_TEST_FILE = tests/unit/

K8S_CHART = ska-oso-oet-umbrella

# unset defaults so settings in pyproject.toml take effect
PYTHON_SWITCHES_FOR_BLACK =
PYTHON_SWITCHES_FOR_ISORT =
PYTHON_LINE_LENGTH = 88

# Pylint tweaks:
# - C = disable msgs about Python conventions
# - R = disable msgs about refactoring
# - W0511(fixme) - these are TODO messages for future improvements
PYTHON_SWITCHES_FOR_PYLINT = --disable=C,R,fixme


up: namespace install-chart wait

dev-up: K8S_CHART_PARAMS = --set ska-oso-oet.rest.image.tag=$(VERSION) \
	--set ska-oso-oet.rest.ingress.enabled=true \
	--set ska-oso-oet.rest.oda.backend.type=filesystem \
	--set ska-oso-oet.rest.oda.url=$(ODA_URI) \
	--set ska-db-oda.enabled=true \
	--set ska-db-oda.pgadmin4.enabled=false

dev-up: k8s-namespace k8s-install-chart k8s-wait ## bring up developer deployment

dev-down: k8s-uninstall-chart k8s-delete-namespace  ## tear down developer deployment

rest:  ## start OET REST server
	docker run --rm -p 5000:5000 -v $(CURDIR):/app -e PYTHONPATH=/app/src -w /app --name=ska-oso-oet-rest $(IMAGE_TO_TEST) python -m ska_oso_oet.main

diagrams:  ## recreate PlantUML diagrams whose source has been modified
	@for i in $$(git diff --name-only -- '*.puml'); \
	do \
		echo "Recreating `dirname $$i`/export/`basename $${i%%.*}.svg`"; \
		cat $$i | docker run --rm -i think/plantuml -tsvg - > `dirname $$i`/export/`basename $${i%%.*}.svg`; \
	done
	docker run --rm -v $(CURDIR):/data rlespinasse/drawio-export:v4.5.0 --format=svg --on-changes --remove-page-suffix docs/src/diagrams

# Set the release tag in the values.yaml and the chart version in the umbrella chart.
# Has to be done after version is set everywhere else because changes in values.yaml are considered
# non-release related changes and so would need to be committed separately. Adding them last avoids
# release change checks and allows to add them as part of the release commit.
helm-post-set-release:
	sed -i"" -e "s/^\([[:blank:]]*\)tag: .*/\1tag: $(VERSION)/" charts/ska-oso-oet/values.yaml
	sed -i"" -e "13s/^\([[:blank:]]*\)version: .*/\1version: $(VERSION)/" charts/ska-oso-oet-umbrella/Chart.yaml

TEST_REPO_SETUP_CMD = "cd /tmp/test_repo; git init; git add .; git -c user.name='Test' -c user.email='test@email.org' commit -am."

# Copy scripts and set up a test git project in the OET container before tests are executed
k8s-pre-test:
	kubectl cp tests/acceptance/ska_oso_oet/scripts/ $(KUBE_NAMESPACE)/ska-oso-oet-rest-$(HELM_RELEASE)-0:/tmp/scripts
	kubectl cp tests/acceptance/ska_oso_oet/test_project/ $(KUBE_NAMESPACE)/ska-oso-oet-rest-$(HELM_RELEASE)-0:/tmp/test_repo
	kubectl -n $(KUBE_NAMESPACE) exec ska-oso-oet-rest-$(HELM_RELEASE)-0 -- bash -c $(TEST_REPO_SETUP_CMD)

k8s-post-test:
	kubectl -n $(KUBE_NAMESPACE) exec ska-oso-oet-rest-$(HELM_RELEASE)-0 -- rm -r /tmp/scripts
	kubectl -n $(KUBE_NAMESPACE) exec ska-oso-oet-rest-$(HELM_RELEASE)-0 -- rm -r /tmp/test_repo

# install helm plugin from https://github.com/helm-unittest/helm-unittest.git
k8s-chart-test:
	mkdir -p charts/build; \
	helm unittest charts/ska-oso-oet/ --with-subchart \
		--output-type JUnit --output-file charts/build/chart_template_tests.xml
