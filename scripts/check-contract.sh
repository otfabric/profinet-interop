#!/bin/sh
# SPDX-License-Identifier: MIT
#
# Checks every adapter image against docs/CONTAINER_CONTRACT.md: version
# prints one line, print-capabilities a capability document with the
# adapter's name, roles and schema version, and an unknown command exits 2.
set -eu
TAG=${1:-dev}
fail=0
for a in pnet pnio-rs profinet-py pnio-dcp scapy tshark umrp mrp; do
	img="profinet-interop-$a:$TAG"
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
' "$a" || { echo "$img: bad capability document: $caps"; fail=1; }
	set +e
	docker run --rm "$img" no-such-command >/dev/null 2>&1
	code=$?
	set -e
	[ "$code" -eq 2 ] || { echo "$img: unknown command exits $code, not 2"; fail=1; }
	echo "$img: $v"
done
exit $fail
