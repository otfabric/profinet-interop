# HELP
# This will output the help for each task
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html

.DEFAULT_GOAL := help

.PHONY: help images image-% capabilities check-versions lint contract matrix smoke clean

ADAPTERS := pnet pnio-rs profinet-py pnio-dcp scapy tshark
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

clean: ## Remove the local images
	-docker rmi $(addsuffix :$(TAG),$(addprefix profinet-interop-,$(ADAPTERS)))
