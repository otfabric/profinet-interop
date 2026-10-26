#!/bin/sh
# $opts below is split into its words on purpose.
# shellcheck disable=SC2086
# profinet-interop adapter for tshark.
#
#   profinet-interop check FILE.pcap   JSON: frames per protocol, malformed
#                                      frames, expert infos of severity
#                                      warning or error
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
print-capabilities) printf '{"schemaVersion":"1.0","adapter":"tshark","implementation":"Wireshark tshark","license":"GPL-2.0-or-later","roles":["decoder"]}\n' ;;
*)
	echo "unknown command ${1:-}: profinet-interop check FILE.pcap | print-capabilities | version" >&2
	exit 2
	;;
esac
