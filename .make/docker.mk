#
# IMAGE_TO_TEST defines the tag of the Docker image to test
#
IMAGE_TO_TEST = $(DOCKER_REGISTRY_HOST)/$(DOCKER_REGISTRY_USER)/$(PROJECT):$(VERSION)

CACHE_VOLUME = $(PROJECT)-test-cache

#
# Never use the network=host mode when running CI jobs, and add extra
# distinguishing identifiers to the network name and container names to
# prevent collisions with jobs from the same project running at the same
# time.
#
ifneq ($(CI_JOB_ID),)
CONTAINER_NAME_PREFIX := $(PROJECT)-$(CI_JOB_ID)-
DOCKER_TOX_CACHE :=
else
CONTAINER_NAME_PREFIX := $(PROJECT)-
DOCKER_TOX_CACHE := -v $(CACHE_VOLUME):/app/.tox
endif

# Creates Docker volume for use as a cache, if it doesn't exist already
INIT_CACHE = \
	docker volume ls | grep $(CACHE_VOLUME) || \
	docker create --name $(CACHE_VOLUME) -v $(CACHE_VOLUME):/app/.tox $(IMAGE_TO_TEST)

# Create Docker volume for storing test reports
#
# See http://cakoose.com/wiki/gnu_make_thunks
BUILD_GEN = $(shell docker create -v /app/build $(IMAGE_TO_TEST))
BUILD = $(eval BUILD := $(BUILD_GEN))$(BUILD)

docker_make = tar -c tests/ | \
	docker run -i --rm \
	-e TANGO_HOST=$(TANGO_HOST) \
	$(DOCKER_TOX_CACHE) -v /app/build -w /app \
	-u tango $(DOCKER_RUN_ARGS) $(IMAGE_TO_TEST) \
	bash -c "sudo chown -R tango:tango /app/build && \
			 sudo chown -fR tango:tango /app/.tox; \
			 tar x -C /app --exclude='*.pyc' --exclude='__pycache__' --strip-components 1 --warning=all && \
			 make HELM_RELEASE=$(RELEASE_NAME) TANGO_HOST=$(TANGO_HOST) MARK=$(MARK) $1" \
	2>&1

unit_test: DOCKER_RUN_ARGS = --volumes-from=$(BUILD)
unit_test: build  ## test the application
	$(INIT_CACHE)
	$(call docker_make,test); \
	status=$$?; \
	docker cp $(BUILD):/app/build .; \
	docker rm -f -v $(BUILD); \
	exit $$status

lint: DOCKER_RUN_ARGS = --volumes-from=$(BUILD)
lint: build  ## lint the application
	$(INIT_CACHE)
	$(call docker_make,lint); \
	status=$$?; \
	docker cp $(BUILD):/app/build .; \
	docker rm -f -v $(BUILD); \
	exit $$status

#
# Defines a default make target so that help is printed if make is called
# without a target
#
.DEFAULT_GOAL := help

pull_release:  ## download the latest release of the application
	docker pull $(DOCKER_REGISTRY_HOST)/$(DOCKER_REGISTRY_USER)/$(PROJECT):$(RELEASE)

interactive: build  ## start an interactive session using the project image (caution: R/W mounts source directory to /app)
	docker run --rm -it --name=$(CONTAINER_NAME_PREFIX)dev -e TANGO_HOST=$(TANGO_HOST) \
	  -v $(CURDIR):/app $(IMAGE_TO_TEST) /bin/bash

prune:  ## delete stale Docker images
	docker images --format '{{.ID}} {{.Repository}}:{{.Tag}}' |\
		grep '$(DOCKER_REGISTRY_HOST)/$(DOCKER_REGISTRY_USER)/$(PROJECT)' |\
		grep -v ':latest$$' |\
		grep -v '$(RELEASE)$$' |\
		grep -v '$(VERSION)$$' |\
		awk '{print $$1;}' |\
		xargs docker rmi -f