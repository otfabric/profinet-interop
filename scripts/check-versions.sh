#!/bin/sh
# Fails when versions.yaml and the Dockerfiles disagree on a pin.
set -eu
cd "$(dirname "$0")/.."
fail=0
check() { # file pattern value
	if ! grep -qx "ARG $2=$3" "$1"; then echo "$1: $2 is not $3 (versions.yaml)"; fail=1; fi
}
yaml() { awk -v impl="$1" -v key="$2" '
	$1 == impl":" { inside = 1; next }
	inside && /^  [a-z]/ { inside = 0 }
	inside && $1 == key":" { gsub(/"/, "", $2); print $2; exit }' versions.yaml; }
# Every Dockerfile names its upstream UPSTREAM_VERSION (a release) and/or
# UPSTREAM_SHA (a commit); "make candidate-<adapter>" overrides them.
check adapters/pnet/Dockerfile UPSTREAM_SHA "$(yaml pnet revision)"
check adapters/pnio-rs/Dockerfile UPSTREAM_VERSION "$(yaml pnio-rs version)"
check adapters/pnio-rs/Dockerfile UPSTREAM_SHA "$(yaml pnio-rs revision)"
check adapters/profinet-py/Dockerfile UPSTREAM_VERSION "$(yaml profinet-py version)"
check adapters/pnio-dcp/Dockerfile UPSTREAM_VERSION "$(yaml pnio-dcp version)"
check adapters/pnio-dcp/Dockerfile UPSTREAM_SHA256 "$(yaml pnio-dcp sha256)"
check adapters/scapy/Dockerfile UPSTREAM_VERSION "$(yaml scapy version)"
[ "$fail" = 0 ] && echo "versions.yaml agrees with the Dockerfiles"
exit "$fail"
