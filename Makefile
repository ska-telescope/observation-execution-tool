#
# Project makefile for a Tango project. You should normally only need to modify
# CAR_OCI_REGISTRY_USER and PROJECT below.
#

#
# DOCKER_REGISTRY_HOST, CAR_OCI_REGISTRY_USER and PROJECT are combined to define
# the Docker tag for this project. The definition below inherits the standard
# value for DOCKER_REGISTRY_HOST (=rnexus.engageska-portugal.pt) and overwrites
# CAR_OCI_REGISTRY_USER and PROJECT to give a final Docker tag of
# nexus.engageska-portugal.pt/tango-example/powersupply
#
CAR_OCI_REGISTRY_HOST ?= artefact.skao.int
CAR_OCI_REGISTRY_USERNAME ?= ska-telescope
PROJECT = ska-oso-oet

# KUBE_NAMESPACE defines the Kubernetes Namespace that will be deployed to
# using Helm.  If this does not already exist it will be created
KUBE_NAMESPACE ?= oet

# RELEASE_NAME is the release that all Kubernetes resources will be labelled
# with
RELEASE_NAME ?= test

# UMBRELLA_CHART_PATH Path of the umbrella chart to work with
UMBRELLA_CHART_PATH ?= charts/oet-umbrella/

# Fixed variables
# Timeout for gitlab-runner when run locally
TIMEOUT = 86400
# Helm version
HELM_VERSION = v3.3.1
# kubectl version
KUBERNETES_VERSION = v1.19.2

# Docker, K8s and Gitlab CI variables
# gitlab-runner debug mode - turn on with non-empty value
RDEBUG ?=
# gitlab-runner executor - shell or docker
EXECUTOR ?= shell
# DOCKER_HOST connector to gitlab-runner - local domain socket for shell exec
DOCKER_HOST ?= unix:///var/run/docker.sock
# DOCKER_VOLUMES pass in local domain socket for DOCKER_HOST
DOCKER_VOLUMES ?= /var/run/docker.sock:/var/run/docker.sock
# registry credentials - user/pass/registry - set these in PrivateRules.mak
CAR_OCI_REGISTRY_USER_LOGIN ?=  ## registry credentials - user - set in PrivateRules.mak
CI_REGISTRY_PASS_LOGIN ?=  ## registry credentials - pass - set in PrivateRules.mak
CI_REGISTRY ?= gitlab.com/ska-telescope/ska-oso-oet

CI_PROJECT_DIR ?= .

KUBE_CONFIG_BASE64 ?=  ## base64 encoded kubectl credentials for KUBECONFIG
KUBECONFIG ?= /etc/deploy/config ## KUBECONFIG location

CAR_PYPI_REPOSITORY_URL ?= https://artefact.skao.int/repository/pypi-internal/simple

# define private overrides for above variables in here
-include PrivateRules.mak

# Test runner - run to completion job in K8s
# name of the pod running the k8s_tests
TEST_RUNNER = oet-$(CI_JOB_ID)-$(KUBE_NAMESPACE)-$(RELEASE_NAME)

#
# include makefile to pick up the standard Make targets, e.g., 'make build'
# build, 'make push' docker push procedure, etc. The other Make targets
# ('make interactive', 'make test', etc.) are defined in this file.
#
include .make/docker.mk
include .make/k8s.mk
include .make/release.mk

up: namespace install-chart wait

down: uninstall-chart delete_namespace

rest:  ## start OET REST server
	docker run --rm -p 5000:5000 -v $(CURDIR):/app -e PYTHONPATH=/app/src -w /app --name=oet-rest $(IMAGE_TO_TEST) python -m oet.procedure.application.main

post-push:
	@. $(RELEASE_SUPPORT) ; differsFromRelease || docker push $(IMAGE):$(VERSION) ;

test: unit_test

.PHONY: all test help k8s show lint deploy delete logs describe namespace delete_namespace kubeconfig kubectl_dependencies helm_dependencies rk8s_test k8s_test rlint install-chart uninstall-chart reinstall-chart upgrade-chart
