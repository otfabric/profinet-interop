# The profinet-interop-otfabric image, from the repository root:
#   make -f own/go-profinet/Makefile image smoke interop
#
# Apart from the top-level Makefile on purpose: this image is not in ADAPTERS
# and not in a release of the harness. No reference image is published: build
# the references first (make image-pnio-dcp image-profinet-py image-pnio-rs).

IMAGE ?= ghcr.io/otfabric/profinet-interop-otfabric:dev
# The local builds of the reference images to test against.
TAG ?= dev
REFERENCES ?= pnio-dcp profinet-py pnio-rs
BASE_REGISTRY ?= docker.io/library

# The latest go-profinet release, as the workflow builds it.
UPSTREAM_VERSION ?= $(shell git ls-remote --tags --refs https://github.com/otfabric/go-profinet.git 'v[0-9]*' | sed 's,.*refs/tags/,,' | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$$' | sort -V | tail -1)
UPSTREAM_SHA ?= $(shell git ls-remote --tags https://github.com/otfabric/go-profinet.git 'refs/tags/$(UPSTREAM_VERSION)^{}' | cut -f1)

export TAG
export GATE = otfabric
export ADAPTER_IMAGE_otfabric = $(IMAGE)

.PHONY: image smoke interop

image:
	docker build --build-arg BASE_REGISTRY=$(BASE_REGISTRY) --build-arg UPSTREAM_VERSION=$(UPSTREAM_VERSION) --build-arg UPSTREAM_SHA=$(UPSTREAM_SHA) --build-arg ADAPTER_VERSION=$(UPSTREAM_VERSION) --tag $(IMAGE) --file own/go-profinet/Dockerfile .

smoke:
	scripts/smoke.sh otfabric

interop:
	scripts/interop.sh otfabric $(REFERENCES)
