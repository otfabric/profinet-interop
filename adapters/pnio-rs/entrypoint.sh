#!/bin/sh
# profinet-interop adapter for pnio-rs (typed_bringup). See
# docs/CONTAINER_CONTRACT.md.
#
#   profinet-interop device [--iface IF] [--station NAME] [--diag SLOT:CH:ERROR]
#   profinet-interop print-gsdml      the device's GSDML on stdout
#   profinet-interop print-capabilities | version
set -eu
RUN=/run/profinet-interop
mkdir -p "$RUN"
cmd=${1:-device}
[ $# -gt 0 ] && shift
case "$cmd" in
version)
	echo "pnio-rs $(cat /licenses/pnio-rs/COMMIT)"
	;;
print-gsdml)
	cat /usr/share/profinet-interop/pnio-rs-sample.xml
	;;
print-capabilities)
	cat <<'JSON'
{"schemaVersion":"1.0","adapter":"pnio-rs","implementation":"pnio-rs","version":"v0.1.0","license":"MIT OR Apache-2.0","roles":["device"],
 "identity":{"vendorId":"0xFFFF","deviceId":"0x0001","gsdml":"print-gsdml"},
 "features":{"dcpIdentify":true,"dcpIdentifyFilters":["all","name"],"dcpGet":false,"dcpSetName":false,"dcpSetIP":"same-suite-only","dcpSignal":false,"dcpReset":false,
   "lldp":false,"connect":true,"frameIdRange":"0x8000-0xBBFF","moduleDiff":false,"readWrite":true,"writeMultiple":true,"readImplicit":true,
   "im0to3":true,"im4":false,"diagnosisRecords":false,"alarms":"low-priority diagnosis only","processAlarms":false,"multipleAR":false,"epm":false,"rpcFragmentation":false}}
JSON
	;;
device)
	iface=eth0
	station=pnio-dev
	extra=""
	while [ $# -gt 0 ]; do
		case "$1" in
		--iface) iface=$2; shift 2 ;;
		--station) station=$2; shift 2 ;;
		--diag) extra="$extra --diag $2"; shift 2 ;;
		*) echo "unknown flag $1" >&2; exit 2 ;;
		esac
	done
	ip=$(ip -4 -o addr show dev "$iface" | awk '{split($4,a,"/"); print a[1]}' | head -n1)
	mac=$(cat "/sys/class/net/$iface/address")
	printf '{"event":"start","adapter":"pnio-rs","iface":"%s","mac":"%s","ip":"%s","station":"%s"}\n' "$iface" "$mac" "$ip" "$station"
	touch "$RUN/ready"
	# shellcheck disable=SC2086
	RUST_LOG=${RUST_LOG:-info} typed_bringup --iface "$iface" --ip "$ip" --station "$station" --stats-every 1 $extra 2>&1 |
		tee "$RUN/pnio-rs.log" |
		mawk -W interactive '
		function ev(name, extra) { printf "{\"event\":\"%s\"%s}\n", name, extra; fflush() }
		/AR state: / { s=$0; sub(/.*AR state: /, "", s); gsub(/"/, "", s); ev("ar-state", ",\"state\":\"" s "\"") }
		/rt stats: / { ev("rt-stats", "") }
		/VERDICT: / { s=$0; sub(/.*VERDICT: /, "", s); ev("verdict", ",\"verdict\":\"" s "\"") }
		'
	;;
*)
	echo "unknown command $cmd" >&2
	exit 2
	;;
esac
