#
# Project makefile for a Tango project. You should normally only need to modify
# DOCKER_REGISTRY_USER and PROJECT below.
#

#
# DOCKER_REGISTRY_HOST, DOCKER_REGISTRY_USER and PROJECT are combined to define
# the Docker tag for this project. The definition below inherits the standard
# value for DOCKER_REGISTRY_HOST (=rnexus.engageska-portugal.pt) and overwrites
# DOCKER_REGISTRY_USER and PROJECT to give a final Docker tag of
# nexus.engageska-portugal.pt/tango-example/powersupply
#
DOCKER_REGISTRY_USER:=ska-telescope
PROJECT = observation-execution-tool

#
# include makefile to pick up the standard Make targets, e.g., 'make build'
# build, 'make push' docker push procedure, etc. The other Make targets
# ('make interactive', 'make test', etc.) are defined in this file.
# 


include .make/Makefile.mk

#
# IMAGE_TO_TEST defines the tag of the Docker image to test
#
IMAGE_TO_TEST = $(DOCKER_REGISTRY_HOST)/$(DOCKER_REGISTRY_USER)/$(PROJECT):latest

#
# CACHE_VOLUME is the name of the Docker volume used to cache eggs and wheels
# used during the test procedure. The volume is not used during the build
# procedure
#
CACHE_VOLUME = $(PROJECT)-test-cache

# optional docker run-time arguments
DOCKER_RUN_ARGS =

#
# Never use the network=host mode when running CI jobs, and add extra
# distinguishing identifiers to the network name and container names to
# prevent collisions with jobs from the same project running at the same
# time.
#
ifneq ($(CI_JOB_ID),)
CONTAINER_NAME_PREFIX := $(PROJECT)-$(CI_JOB_ID)-
else
CONTAINER_NAME_PREFIX := $(PROJECT)-
endif

ifeq ($(OS),Windows_NT)
    $(error Sorry, Windows is not supported yet)
else
	UNAME_S := $(shell uname -s)
	ifeq ($(UNAME_S),Linux)
		DISPLAY ?= :0.0

		XAUTHORITY_MOUNT := /tmp/.X11-unix:/tmp/.X11-unix
		XAUTHORITY ?= /hosthome/.Xauthority
		# /bin/sh (=dash) does not evaluate 'docker network' conditionals correctly
		SHELL := /bin/bash
	endif
	ifeq ($(UNAME_S),Darwin)
		IF_INTERFACE := $(shell netstat -nr -f inet | awk '{ if ($$1 ~/default/ && $$4 ~/en/) { print $$4} }')
		DISPLAY := $(shell ifconfig $(IF_INTERFACE) | awk '{ if ($$1 ~/inet$$/) { print $$2} }'):0
		XAUTHORITY_MOUNT := $(HOME):/hosthome:ro
		XAUTHORITY := /hosthome/.Xauthority
	endif
endif

# distinguish the bridge network from others by adding the project name
TANGO_HOST := $(CONTAINER_NAME_PREFIX)databaseds:10000
MYSQL_HOST := $(CONTAINER_NAME_PREFIX)tangodb:3306


#
# Defines a default make target so that help is printed if make is called
# without a target
#
.DEFAULT_GOAL := help

#
# defines a function to copy test-harness
# and then runs the requestedtest-harness
#
#   1. attached to the networtest-harness
#   2. uses a persistent volutest-harness
#      downloads are requiredtest-harness
#   3. uses a transient volume as a working directory, in which untarred files
#      and test output can be written in the container and subsequently copied
#      to the host
#
make = tar -c test-harness/ | \
	   docker run -i --rm \
	   -e TANGO_HOST=$(TANGO_HOST) \
	   -v $(CACHE_VOLUME):/home/tango/.cache \
	   -v /build -w /build -u tango $(DOCKER_RUN_ARGS) $(IMAGE_TO_TEST) \
	   bash -c "sudo chown -R tango:tango /build && \
	   tar x --strip-components 1 --warning=all && \
	   make TANGO_HOST=$(TANGO_HOST) $1"

test: DOCKER_RUN_ARGS = --volumes-from=$(BUILD)
test: ## test the application
	$(INIT_CACHE)
	$(call make,test); \
	  status=$$?; \
	  rm -fr build; \
	  docker cp $(BUILD):/build .; \
	  docker rm -f -v $(BUILD); \
	  exit $$status
	  
lint: DOCKER_RUN_ARGS = --volumes-from=$(BUILD)
lint: ## lint the application (static code analysis)
	$(INIT_CACHE)
	$(call make,lint); \
	  rm -fr build; \
	  docker cp $(BUILD):/build .; \
	  docker rm -f -v $(BUILD); \
	  exit 0

test-all: DOCKER_RUN_ARGS = --volumes-from=$(BUILD)
test-all: ## test and lint the application
	$(INIT_CACHE)
	$(call make,test-all); \
	  status=$$?; \
	  rm -fr build; \
	  docker cp $(BUILD):/build .; \
	  docker rm -f -v $(BUILD); \
	  exit $$status


pull:  ## download the application image
	docker pull $(IMAGE_TO_TEST)

up: build  ## start develop/test environment

piplock: build  ## overwrite Pipfile.lock with the image version
	docker run $(IMAGE_TO_TEST) cat /app/Pipfile.lock > $(CURDIR)/Pipfile.lock

interactive: up
interactive:  ## start an interactive session using the project image (caution: R/W mounts source directory to /app)
	docker run --rm -it -p 3000:3000 --name=$(CONTAINER_NAME_PREFIX)dev -e TANGO_HOST=$(TANGO_HOST)  \
	  -e OET_REST_URI=http://$(shell hostname):5000/api/v1.0/procedures -v $(CURDIR):/app $(IMAGE_TO_TEST) /bin/bash

down:  ## stop develop/test environment and any interactive session
	docker ps | grep $(CONTAINER_NAME_PREFIX)dev && docker stop $(PROJECT)-dev || true

rest: up  ## start OET REST server
	docker run --rm -e FLASK_ENV=development -e FLASK_APP=oet/procedure/application/restserver:create_app -p 5000:5000 --name=oet-rest $(IMAGE_TO_TEST) flask run -h 0.0.0.0

help:  ## show this help.
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

post-push:
	@. $(RELEASE_SUPPORT) ; differsFromRelease || docker push $(IMAGE):$(VERSION) ;

.PHONY: all test up down help

# Creates Docker volume for use as a cache, if it doesn't exist already
INIT_CACHE = \
	docker volume ls | grep $(CACHE_VOLUME) || \
	docker create --name $(CACHE_VOLUME) -v $(CACHE_VOLUME):/cache $(IMAGE_TO_TEST)

# http://cakoose.com/wiki/gnu_make_thunks
BUILD_GEN = $(shell docker create -v /build $(IMAGE_TO_TEST))
BUILD = $(eval BUILD := $(BUILD_GEN))$(BUILD)
