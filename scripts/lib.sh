#!/usr/bin/env bash
# Shared helpers of the self-test scripts. Source, do not execute.
#
# No image of this repository is published (versions.yaml): the references
# are local builds, profinet-interop-<adapter>:$TAG (make images).

TAG="${TAG:-dev}"

log() { echo "[$(basename "$0" .sh)] $*" >&2; }

# image_of <adapter>: ADAPTER_IMAGE_<adapter> (a dash is an underscore)
# names an image outside the release set, such as profinet-interop-otfabric,
# which this repository's scripts know nothing about.
image_of() {
    local override="ADAPTER_IMAGE_${1//-/_}"
    if [[ -n "${!override:-}" ]]; then echo "${!override}"; else echo "profinet-interop-$1:${TAG}"; fi
}

require_tools() {
    local t
    for t in docker python3; do
        command -v "$t" >/dev/null || { log "missing required tool: $t"; exit 2; }
    done
}
