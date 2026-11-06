#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
#
# Checks adapter images against docs/CONTAINER_CONTRACT.md: version prints
# one line, print-capabilities a capability document with the adapter's
# name, roles, schema version and (since contract 1.3) its upstream with
# independentEngine, and an unknown command exits 2.
#
# Usage: scripts/check-contract.sh [TAG] [adapter...]   (default: every adapter)
# Images: scripts/lib.sh's image_of (ADAPTER_IMAGE_<adapter> or profinet-interop-<adapter>:TAG).
set -eu
TAG=${1:-dev}
[ $# -gt 0 ] && shift
# shellcheck source=scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
adapters=("$@")
[ ${#adapters[@]} -gt 0 ] || adapters=(pnet pnio-rs profinet-py pnio-dcp scapy tshark umrp mrp netsnmp)
fail=0
for a in "${adapters[@]}"; do
	img=$(image_of "$a")
	v=$(docker run --rm "$img" version)
	[ "$(printf '%s\n' "$v" | wc -l)" -eq 1 ] || { echo "$img: version is not one line: $v"; fail=1; }
	caps=$(docker run --rm "$img" print-capabilities)
	printf '%s' "$caps" | python3 -c '
import json, sys
d = json.load(sys.stdin)
a = sys.argv[1]
assert d.get("schemaVersion") == "1.0", "schemaVersion"
assert d.get("adapter") == a, "adapter %r" % d.get("adapter")
assert isinstance(d.get("roles"), list) and d["roles"], "roles"
u = d.get("upstream")
assert isinstance(u, dict) and u.get("name") and "version" in u, "upstream"
assert isinstance(u.get("independentEngine"), bool), "upstream.independentEngine"
' "$a" || { echo "$img: bad capability document: $caps"; fail=1; }
	set +e
	docker run --rm "$img" no-such-command >/dev/null 2>&1
	code=$?
	set -e
	[ "$code" -eq 2 ] || { echo "$img: unknown command exits $code, not 2"; fail=1; }
	echo "$img: $v"
done
exit $fail
