# HELP
# This will output the help for each task
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html

.DEFAULT_GOAL := help

.PHONY: help images image-% capabilities check-versions lint contract matrix smoke versions release-notes latest-upstream clean FORCE

ADAPTERS := pnet pnio-rs profinet-py pnio-dcp scapy tshark umrp mrp netsnmp
TAG ?= dev

help: ## This help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9_%-]+:.*?## / {printf "\033[36m%-24s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

images: $(addprefix image-,$(ADAPTERS)) ## Build every adapter image as profinet-interop-<adapter>:$(TAG)

image-%: ## Build one adapter image, e.g. make image-pnet
	docker build -t profinet-interop-$*:$(TAG) adapters/$*

capabilities: ## Print the capability document of every image
	@for a in $(ADAPTERS); do docker run --rm profinet-interop-$$a:$(TAG) print-capabilities; done

check-versions: ## Fail when versions.yaml disagrees with the Dockerfiles
	@scripts/check-versions.sh

lint: ## Shellcheck the entrypoints and scripts; compile the Python adapters
	@shellcheck adapters/*/entrypoint.sh adapters/tshark/check.sh adapters/pnet/set_network_parameters adapters/pnet/set_profinet_leds scripts/*.sh
	@python3 -m py_compile adapters/*/*.py scripts/*.py

contract: ## Check every image against the command-line contract (docs/CONTAINER_CONTRACT.md)
	@scripts/check-contract.sh $(TAG)

matrix: ## Regenerate docs/MATRIX.md and matrix/results.json from RESULTS=dir (go-profinet's interop results)
	@python3 scripts/matrix.py "$(RESULTS)" matrix/results.json docs/MATRIX.md

smoke: images ## Build the images and print their versions
	@for a in $(ADAPTERS); do docker run --rm profinet-interop-$$a:$(TAG) version; done

versions: ## Print the version of every built image
	@for a in $(ADAPTERS); do docker run --rm profinet-interop-$$a:$(TAG) version; done

# ── Upstream candidates ───────────────────────────────────────────────────────
# Builds one adapter on another upstream than its pin and checks it with the
# smoke test (version), its capability document and the contract, against
# the other adapters at their pins (built first: make images). There is no
# cross-stack self-test in this repository: go-profinet's interop suite is
# the behavioural test. Every adapter Dockerfile takes its upstream as the
# build argument UPSTREAM_VERSION (a release: pnio-rs, profinet-py,
# pnio-dcp, scapy) and/or UPSTREAM_SHA (a commit: pnet, pnio-rs). At the pin
# the release build and its hash checks apply unchanged; any other value
# takes the Dockerfile's candidate path, which says "candidate build: ..."
# on stderr. tshark and netsnmp are Debian bookworm packages: no candidate
# build.
# scripts/latest-upstream.py prints the latest upstream of every adapter.
# Release pins are never modified.

CANDIDATE_VERSION ?=
CANDIDATE_SHA     ?=
CANDIDATE_SHA256  ?=
COMMIT_PINNED     := pnet pnio-rs umrp mrp

latest-upstream: ## Compare every pin with the latest upstream (decision table; JSON=file writes JSON too)
	@scripts/latest-upstream.py $(if $(JSON),--json $(JSON))

candidate-%: FORCE ## Build one adapter on CANDIDATE_VERSION / CANDIDATE_SHA [/ CANDIDATE_SHA256] and check it, e.g. candidate-scapy CANDIDATE_VERSION=2.8.0
	@case " $(ADAPTERS) " in *" $* "*) ;; *) echo "Error: no adapter $* (one of: $(ADAPTERS))"; exit 1 ;; esac
	@if [ "$*" = tshark ] || [ "$*" = netsnmp ]; then echo "Error: $* is a Debian bookworm package, pinned by Debian: a rebuild (make image-$*) installs the current one"; exit 1; fi
	@case " $(COMMIT_PINNED) " in \
		*" $* "*) echo "$(CANDIDATE_SHA)" | grep -qE '^[0-9a-f]{40}$$' || { echo "Error: CANDIDATE_SHA=<the upstream commit, 40 hex digits> is required (scripts/latest-upstream.py $* prints it as latest_sha)"; exit 1; } ;; \
		*) test -n "$(CANDIDATE_VERSION)" || { echo "Error: CANDIDATE_VERSION=<upstream version> is required (scripts/latest-upstream.py $* prints it as latest)"; exit 1; } ;; \
	esac
	@echo "Building $* candidate on $(or $(CANDIDATE_VERSION),-) $(CANDIDATE_SHA)..."
	docker build \
		$(if $(CANDIDATE_VERSION),--build-arg UPSTREAM_VERSION=$(CANDIDATE_VERSION)) \
		$(if $(CANDIDATE_SHA),--build-arg UPSTREAM_SHA=$(CANDIDATE_SHA)) \
		$(if $(CANDIDATE_SHA256),--build-arg UPSTREAM_SHA256=$(CANDIDATE_SHA256)) \
		-t profinet-interop-$*:candidate adapters/$*
	@for a in $(filter-out $*,$(ADAPTERS)); do docker tag profinet-interop-$$a:$(TAG) profinet-interop-$$a:candidate || exit 1; done
	@echo "Smoke:"; for a in $(ADAPTERS); do docker run --rm profinet-interop-$$a:candidate version || exit 1; done
	@echo "Capabilities of the candidate:"; docker run --rm profinet-interop-$*:candidate print-capabilities
	@echo "Contract:"; scripts/check-contract.sh candidate

FORCE:

release-notes: ## Print the notes of VERSION=vX.Y.Z (default: the version versions.yaml names) from RELEASE.md
	@scripts/release-notes.sh $(VERSION)

clean: ## Remove the local images (and the candidate tags)
	-docker rmi $(addsuffix :$(TAG),$(addprefix profinet-interop-,$(ADAPTERS)))
	-docker rmi $(addsuffix :candidate,$(addprefix profinet-interop-,$(ADAPTERS))) 2>/dev/null
