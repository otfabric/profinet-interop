#!/bin/sh
# $opts below is split into its words on purpose.
# shellcheck disable=SC2086
# profinet-interop adapter for tshark.
#
#   profinet-interop check FILE.pcap   JSON: frames per protocol, malformed
#                                      frames, expert infos of severity
#                                      warning or error
#   profinet-interop fields FILE.pcap FILTER FIELD...
#                                      JSON (contract 1.4): per frame that
#                                      matches the display filter, every
#                                      occurrence of each field as tshark
#                                      prints it
#   profinet-interop print-capabilities | version
set -eu
case "${1:-}" in
version) tshark --version | head -1 ;;
check)
	[ $# -eq 2 ] || { echo "usage: profinet-interop check FILE.pcap" >&2; exit 2; }
	f=$2
	# PNIO RPC is connectionless DCE/RPC on UDP 34964, but its responses,
	# and the device's own requests to the controller, use ephemeral ports.
	# tshark picks a dissector by port first, so an ephemeral port that
	# belongs to another protocol (37008, TZSP, for one) turned valid RPC
	# into "malformed" frames. The DCE/RPC heuristic recognises RPC on any
	# port when heuristics go first. WireGuard's heuristic would take some
	# packets, so it stays off.
	opts="--disable-protocol wg -o udp.try_heuristic_first:TRUE -o dcerpc.desegment_dcerpc:TRUE"
	exec 2>/dev/null
	total=$(tshark -n $opts -r "$f" -T fields -e frame.number | wc -l)
	protos=$(tshark -n $opts -r "$f" -T fields -e _ws.col.Protocol | sort | uniq -c | awk 'BEGIN{printf "{"} {if (NR>1) printf ","; printf "\"%s\":%d", $2, $1} END{printf "}"}')
	malformed=$(tshark -n $opts -r "$f" -Y '_ws.malformed' -T fields -e frame.number -e _ws.col.Info | jq -R -s -c 'split("\n") | map(select(length>0) | split("\t") | {frame: (.[0]|tonumber), info: .[1]})')
	expert=$(tshark -n $opts -r "$f" -Y '_ws.expert.severity >= 6291456' -T fields -e frame.number -e _ws.expert.message -e _ws.col.Protocol | jq -R -s -c 'split("\n") | map(select(length>0) | split("\t") | {frame: (.[0]|tonumber), message: .[1], protocol: .[2]})')
	printf '{"schemaVersion":"1.0","adapter":"tshark","version":"%s","frames":%s,"byProtocol":%s,"malformed":%s,"expert":%s}\n' \
		"$(tshark --version 2>/dev/null | head -1 | awk '{print $3}')" "$total" "$protos" "$malformed" "$expert"
	;;
fields)
	[ $# -ge 4 ] || { echo "usage: profinet-interop fields FILE.pcap FILTER FIELD..." >&2; exit 2; }
	f=$2
	filter=$3
	shift 3
	[ -r "$f" ] || { echo "fields: cannot read $f" >&2; exit 2; }
	opts="--disable-protocol wg -o udp.try_heuristic_first:TRUE -o dcerpc.desegment_dcerpc:TRUE"
	for x in "$@"; do
		case "$x" in
		*[!A-Za-z0-9_.-]* | "")
			echo "fields: bad field name: $x" >&2
			exit 2
			;;
		esac
	done
	# One tshark run per field: a line per matching frame, its number and,
	# after a tab, every occurrence of the field in frame order, separated
	# by commas (tshark 4.0 has no tab as aggregator; the numeric fields
	# this is for never contain one). A filter or a field tshark does not
	# know is a usage error.
	lines=""
	for x in "$@"; do
		out=$(tshark -n $opts -r "$f" -Y "$filter" -T fields -E separator=/t -E occurrence=a -E aggregator=, -e frame.number -e "$x" 2>/dev/null) || {
			echo "fields: tshark refused the filter or the field: $filter $x" >&2
			exit 2
		}
		lines=$(printf '%s\n%s' "$lines" "$(printf '%s\n' "$out" | jq -R -c --arg name "$x" 'select(length > 0) | split("\t") | {name: $name, frame: (.[0] | tonumber), values: (.[1] // "" | split(",") | map(select(length > 0)))}')")
	done
	printf '%s\n' "$lines" | jq -s -c --arg v "$(tshark --version 2>/dev/null | head -1 | awk '{print $3}')" --arg filter "$filter" '
		{schemaVersion: "1.0", adapter: "tshark", version: $v, filter: $filter,
		 frames: (group_by(.frame) | map({frame: .[0].frame, fields: (map({(.name): .values}) | add)}))}'
	;;
print-capabilities) printf '{"schemaVersion":"1.0","adapter":"tshark","implementation":"Wireshark tshark","license":"GPL-2.0-or-later","roles":["decoder"],"upstream":{"name":"Wireshark tshark","version":"%s","independentEngine":true}}\n' "$(tshark --version 2>/dev/null | head -1 | awk '{print $3}')" ;;
*)
	echo "unknown command ${1:-}: profinet-interop check FILE.pcap | fields FILE.pcap FILTER FIELD... | print-capabilities | version" >&2
	exit 2
	;;
esac
