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
MAJOR_VERSION=$(shell cut -d'.' -f1 <<< $(VERSION))

# Set sphinx documentation build to fail on warnings (as it is configured
# in .readthedocs.yaml as well)
DOCS_SPHINXOPTS ?= -W --keep-going

# include makefile to pick up the standard Make targets from the submodule
-include .make/base.mk
-include .make/python.mk
-include .make/oci.mk
-include .make/k8s.mk
-include .make/helm.mk

# include your own private variables for custom deployment configuration
-include PrivateRules.mak

IMAGE_TO_TEST = $(CAR_OCI_REGISTRY_HOST)/$(strip $(OCI_IMAGE)):$(VERSION)

ODA_URL ?= http://ska-db-oda-rest-$(RELEASE_NAME):5000/$(KUBE_NAMESPACE)/oda/api/v6
SEMANTIC_VALIDATION=true
POSTGRES_HOST ?= $(RELEASE_NAME)-postgresql
# TODO BTN-2449 will extract this
ADMIN_POSTGRES_PASSWORD ?= secretpassword


K8S_CHART_PARAMS = --set ska-oso-oet.rest.oda.url=$(ODA_URL)
K8S_CHART_PARAMS += --set ska-oso-oet.semantic_validation=true

# For the test, dev and integration environment, use the freshly built image in the GitLab registry
ENV_CHECK := $(shell echo $(CI_ENVIRONMENT_SLUG) | egrep 'test|dev|integration')
ifneq ($(ENV_CHECK),)
K8S_CHART_PARAMS += --set ska-oso-oet.rest.image.tag=$(VERSION)-dev.c$(CI_COMMIT_SHORT_SHA) \
	--set ska-oso-oet.rest.image.registry=$(CI_REGISTRY)/ska-telescope/oso/ska-oso-oet \
	--set ska-oso-oet.rest.ingress.enabled=true 
endif

# For the staging environment, make k8s-install-chart-car will pull the chart from CAR so we do not need to
# change any values
ENV_CHECK := $(shell echo $(CI_ENVIRONMENT_SLUG) | egrep 'staging')
ifneq ($(ENV_CHECK),)
K8S_CHART_PARAMS += --set ska-oso-oet.rest.ingress.enabled=true
endif

# Set cluster_domain to minikube default (cluster.local) in local development
# (CI_ENVIRONMENT_SLUG should only be defined when running on the CI/CD pipeline)
ifeq ($(CI_ENVIRONMENT_SLUG),)
K8S_CHART_PARAMS += --set global.cluster_domain="cluster.local"
endif

# The OET_URL is used by the OET client which runs inside the test pod during k8s-test. We set it explicitly here rather than rely on
# the default in the client, to ensure we are pointing at this instance of the OET
OET_URL ?= http://ska-oso-oet-rest-test:5000/$(KUBE_NAMESPACE)/oet/api/v$(MAJOR_VERSION)
# Set the k8s test command run inside the testing pod to only run the acceptance
# tests (no k8s pod deployment required for unit tests)
K8S_TEST_TEST_COMMAND = OET_URL=$(OET_URL) POSTGRES_HOST=$(POSTGRES_HOST) ADMIN_POSTGRES_PASSWORD=$(ADMIN_POSTGRES_PASSWORD) KUBE_NAMESPACE=$(KUBE_NAMESPACE) pytest ./tests/acceptance | tee pytest.stdout

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

dev-up: K8S_CHART_PARAMS += --set ska-oso-oet.rest.image.tag=$(VERSION) \
	--set ska-oso-oet.rest.ingress.enabled=true \
	--set ska-oso-oet.rest.skuid.url=http://ska-ser-skuid-test-svc:9870 \
	--set ska-oso-oet.rest.oda.backendType=filesystem


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

TEST_REPO_SETUP_CMD = "cd /tmp/test_repo; git init; git add .; git -c user.name='Test' -c user.email='test@email.org' commit -am."

# Copy scripts and set up a test git project in the OET container before tests are executed
k8s-pre-test:
	kubectl cp tests/acceptance/ska_oso_oet/scripts/ $(KUBE_NAMESPACE)/ska-oso-oet-rest-$(HELM_RELEASE)-0:/tmp/scripts
	kubectl cp tests/acceptance/ska_oso_oet/test_project/ $(KUBE_NAMESPACE)/ska-oso-oet-rest-$(HELM_RELEASE)-0:/tmp/test_repo
	kubectl -n $(KUBE_NAMESPACE) exec ska-oso-oet-rest-$(HELM_RELEASE)-0 -- bash -c $(TEST_REPO_SETUP_CMD)

k8s-post-test:
	kubectl -n $(KUBE_NAMESPACE) exec ska-oso-oet-rest-$(HELM_RELEASE)-0 -- rm -r /tmp/scripts
	kubectl -n $(KUBE_NAMESPACE) exec ska-oso-oet-rest-$(HELM_RELEASE)-0 -- rm -r /tmp/test_repo

# The docs build fails unless the ska-oso-oet package is installed locally as importlib.metadata.version requires it.
docs-pre-build:
	poetry install --only-root

# install helm plugin from https://github.com/helm-unittest/helm-unittest.git
k8s-chart-test:
	mkdir -p charts/build; \
	helm unittest charts/ska-oso-oet/ --with-subchart \
		--output-type JUnit --output-file charts/build/chart_template_tests.xml
