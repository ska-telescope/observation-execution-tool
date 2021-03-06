#
#   Copyright 2015  Xebia Nederland B.V.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
ifeq ($(strip $(PROJECT)),)
  NAME=$(shell basename $(CURDIR))
else
  NAME=$(PROJECT)
endif

RELEASE_SUPPORT := $(shell dirname $(abspath $(lastword $(MAKEFILE_LIST))))/.make-release-support

ifeq ($(strip $(DOCKER_REGISTRY_HOST)),)
  DOCKER_REGISTRY_HOST = nexus.engageska-portugal.pt
endif

ifeq ($(strip $(DOCKER_REGISTRY_USER)),)
  DOCKER_REGISTRY_USER = ska-docker
endif

IMAGE=$(DOCKER_REGISTRY_HOST)/$(DOCKER_REGISTRY_USER)/$(NAME)

VERSION=$(shell . $(RELEASE_SUPPORT) ; getVersion)
TAG=$(shell . $(RELEASE_SUPPORT); getTag)
RELEASE=$(shell . $(RELEASE_SUPPORT); getRelease)

SHELL=/bin/bash

DOCKER_BUILD_CONTEXT=.
DOCKER_FILE_PATH=Dockerfile

.PHONY: pre-build docker-build post-build build release patch-release minor-release major-release tag check-status check-release showver \
	push pre-push do-push post-push

build: pre-build docker-build post-build  ## build the application image

pre-build:

post-build:

pre-push:

post-push:

docker-build: .release
	docker build $(DOCKER_BUILD_ARGS) -t $(IMAGE):$(VERSION) $(DOCKER_BUILD_CONTEXT) -f $(DOCKER_FILE_PATH) --build-arg DOCKER_REGISTRY_HOST=$(DOCKER_REGISTRY_HOST) --build-arg DOCKER_REGISTRY_USER=$(DOCKER_REGISTRY_USER)
	docker tag $(IMAGE):$(VERSION) $(IMAGE):latest

.release:
	@echo "release=0.0.0" > .release
	@echo "tag=$(NAME)-0.0.0" >> .release
	@echo INFO: .release created
	@cat .release

release: check-status check-release build

push: pre-push do-push post-push  ## push the image to the Docker registry

do-push:
	docker push $(IMAGE):$(VERSION)
	docker push $(IMAGE):latest

snapshot: build push

showver: .release
	@. $(RELEASE_SUPPORT); getVersion

bump-patch-release: VERSION := $(shell . $(RELEASE_SUPPORT); nextPatchLevel)
bump-patch-release: .release tag

bump-minor-release: VERSION := $(shell . $(RELEASE_SUPPORT); nextMinorLevel)
bump-minor-release: .release tag

bump-major-release: VERSION := $(shell . $(RELEASE_SUPPORT); nextMajorLevel)
bump-major-release: .release tag

patch-release: bump-patch-release release
	@echo $(VERSION)

minor-release: bump-minor-release release
	@echo $(VERSION)

major-release: bump-major-release release
	@echo $(VERSION)

tag: TAG=$(shell . $(RELEASE_SUPPORT); getTag $(VERSION))
tag: check-status
	@. $(RELEASE_SUPPORT) ; ! tagExists $(TAG) || (echo "ERROR: tag $(TAG) for version $(VERSION) already tagged in git" >&2 && exit 1) ;
	@. $(RELEASE_SUPPORT) ; setRelease $(VERSION)
	git add .
	git commit -m "bumped to version $(VERSION)" ;
	git tag $(TAG) ;
	@ if [ -n "$(shell git remote -v)" ] ; then git push --tags ; else echo 'no remote to push tags to' ; fi
	@ if [ -n "$(shell git remote -v)" ] ; then git push --follow-tags ; else echo 'no remote to push code to' ; fi

check-status:
	@. $(RELEASE_SUPPORT) ; ! hasChanges || (echo "ERROR: there are still outstanding changes" >&2 && exit 1) ;

check-release: .release
	@. $(RELEASE_SUPPORT) ; tagExists $(TAG) || (echo "ERROR: version not yet tagged in git. make [minor,major,patch]-release." >&2 && exit 1) ;
	@. $(RELEASE_SUPPORT) ; ! differsFromRelease $(TAG) || (echo "ERROR: current directory differs from tagged $(TAG). make [minor,major,patch]-release." ; exit 1)
