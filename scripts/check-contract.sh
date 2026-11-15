#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
#
# Checks adapter images against docs/CONTAINER_CONTRACT.md: version prints
# one line, print-capabilities a capability document with the adapter's
# name that is valid against schemas/capabilities.schema.json
# (scripts/check-capabilities.py: schema version, roles, features, and since
# contract 1.3 its upstream with independentEngine), and an unknown command
# exits 2. Needs Python's jsonschema package (pip install jsonschema==4.26.0).
#
# Usage: scripts/check-contract.sh [TAG] [adapter...]   (default: every adapter)
# Images: scripts/lib.sh's image_of (ADAPTER_IMAGE_<adapter> or profinet-interop-<adapter>:TAG).
set -eu
TAG=${1:-dev}
[ $# -gt 0 ] && shift
# shellcheck source=scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
python3 -c 'import jsonschema' 2>/dev/null \
	|| { echo "check-contract: the capability check needs the jsonschema package (pip install jsonschema==4.26.0)" >&2; exit 2; }
adapters=("$@")
[ ${#adapters[@]} -gt 0 ] || adapters=(pnet pnio-rs profinet-py pnio-dcp scapy tshark umrp mrp netsnmp)
fail=0
for a in "${adapters[@]}"; do
	img=$(image_of "$a")
	v=$(docker run --rm "$img" version)
	[ "$(printf '%s\n' "$v" | wc -l)" -eq 1 ] || { echo "$img: version is not one line: $v"; fail=1; }
	caps=$(docker run --rm "$img" print-capabilities)
	printf '%s' "$caps" | python3 "$(dirname "${BASH_SOURCE[0]}")/check-capabilities.py" "$a" \
		|| { echo "$img: bad capability document: $caps"; fail=1; }
	set +e
	docker run --rm "$img" no-such-command >/dev/null 2>&1
	code=$?
	set -e
	[ "$code" -eq 2 ] || { echo "$img: unknown command exits $code, not 2"; fail=1; }
	echo "$img: $v"
done
exit $fail
