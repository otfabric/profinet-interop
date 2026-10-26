#!/bin/sh
# profinet-interop adapter for p-net (pn_dev). See docs/CONTAINER_CONTRACT.md.
#
#   profinet-interop device [--iface IF] [--station NAME]
#       Runs pn_dev as an IO-Device and writes one JSON event per line on
#       stdout (the raw log goes to /run/profinet-interop/pn_dev.log).
#   profinet-interop button2
#       Presses the sample app's button 2, which cycles through its process
#       alarm, diagnosis and logbook actions (one step per press).
#   profinet-interop print-capabilities
#   profinet-interop version
set -eu
RUN=/run/profinet-interop
mkdir -p "$RUN"
cmd=${1:-device}
[ $# -gt 0 ] && shift

capabilities() {
	cat <<'JSON'
{"schemaVersion":"1.0","adapter":"pnet","implementation":"p-net","version":"ea5e5540b2be55c4dfadffda39b948632c104daa","license":"GPL-3.0-only","roles":["device"],
 "identity":{"vendorId":"0x0493","deviceId":"0x0002","dapModuleIdent":"0x00000001","modules":[
   {"ident":"0x00000030","submodule":"0x00000130","in":1,"out":0},
   {"ident":"0x00000031","submodule":"0x00000131","in":0,"out":1},
   {"ident":"0x00000032","submodule":"0x00000132","in":1,"out":1},
   {"ident":"0x00000040","submodule":"0x00000140","in":8,"out":8}],
   "parameterRecords":[123,124],"orderId":"12345 Abcdefghijk"},
 "features":{"dcpIdentify":true,"dcpGet":true,"dcpSetName":true,"dcpSetIP":true,"dcpSignal":true,"dcpReset":true,"lldp":true,
   "connect":true,"rtClass1Legacy":true,"rtClass2Advanced":true,"moduleDiff":true,"readWrite":true,"writeMultiple":true,"readImplicit":true,
   "im0to4":true,"diagnosisRecords":true,"alarms":true,"processAlarms":true,"iosar":false,"multipleIOCAR":false,"epm":true}}
JSON
}

case "$cmd" in
version)
	echo "p-net $(cat /licenses/p-net/COMMIT)"
	;;
print-capabilities)
	capabilities
	;;
button2)
	echo 1 >"$RUN/button2"
	sleep 0.3
	echo 0 >"$RUN/button2"
	;;
device)
	iface=eth0
	station=rt-labs-dev
	while [ $# -gt 0 ]; do
		case "$1" in
		--iface) iface=$2; shift 2 ;;
		--station) station=$2; shift 2 ;;
		*) echo "unknown flag $1" >&2; exit 2 ;;
		esac
	done
	echo 0 >"$RUN/button1"
	echo 0 >"$RUN/button2"
	rm -f "$PNET_STORAGE"/pnet_data_*.bin
	mac=$(cat "/sys/class/net/$iface/address")
	ip=$(ip -4 -o addr show dev "$iface" | awk '{print $4}' | head -n1)
	printf '{"event":"start","adapter":"pnet","iface":"%s","mac":"%s","ip":"%s","station":"%s"}\n' "$iface" "$mac" "$ip" "$station"
	touch "$RUN/ready"
	# pn_dev's log lines become JSON events; everything is kept in the log.
	# mawk reads a pipe in blocks unless interactive, which delays the events.
	stdbuf -oL pn_dev -vvvv -i "$iface" -s "$station" -p "$PNET_STORAGE" -b "$RUN/button1" -d "$RUN/button2" 2>&1 |
		tee "$RUN/pn_dev.log" |
		mawk -W interactive '
		function ev(name, extra) { printf "{\"event\":\"%s\"%s}\n", name, extra; fflush() }
		/PLC connect indication/ { ev("connect", "") }
		/PLC dcontrol message/ { ev("prmend", "") }
		/PLC ccontrol message confirmation/ { ev("appready-confirmed", "") }
		/PLC release \(disconnect\) indication/ { ev("release", "") }
		/Connection \(AREP [0-9]+\) closed/ { ev("closed", "") }
		/Cyclic data transmission started/ { ev("cyclic-started", "") }
		/Event indication .*ABORT/ { ev("abort", "") }
		/Profinet signal LED indication/ { ev("signal", "") }
		/PLC reset indication/ { ev("reset", "") }
		/PLC write record indication/ { getline l; match(l, /Index: [0-9]+/); ev("write", ",\"index\":" substr(l, RSTART+7, RLENGTH-7)) }
		/PLC read record indication/ { getline l; match(l, /Index: [0-9]+/); ev("read", ",\"index\":" substr(l, RSTART+7, RLENGTH-7)) }
		/Plug submodule\./ { match($0, /Slot: *[0-9]+/); s=substr($0, RSTART+5, RLENGTH-5); gsub(/ /, "", s); ev("plug-submodule", ",\"slot\":" s) }
		/PLC alarm ACK confirmation/ { ev("alarm-ack-confirmed", "") }
		/PLC alarm confirmation/ { ev("alarm-confirmed", "") }
		/Sending process alarm/ { ev("process-alarm-sent", "") }
		/Adding standard diagnosis/ { ev("diagnosis-added", "") }
		/Removing standard diagnosis/ { ev("diagnosis-removed", "") }
		'
	;;
*)
	echo "unknown command $cmd" >&2
	exit 2
	;;
esac
