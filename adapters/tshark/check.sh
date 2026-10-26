#!/bin/sh
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
	f=$2
	# UDP 34964 is DCE/RPC; WireGuard's heuristic would take some packets.
	opts="--disable-protocol wg -o dcerpc.desegment_dcerpc:TRUE"
	exec 2>/dev/null
	total=$(tshark -n $opts -r "$f" -T fields -e frame.number | wc -l)
	protos=$(tshark -n $opts -r "$f" -T fields -e _ws.col.Protocol | sort | uniq -c | awk 'BEGIN{printf "{"} {if (NR>1) printf ","; printf "\"%s\":%d", $2, $1} END{printf "}"}')
	malformed=$(tshark -n $opts -r "$f" -Y '_ws.malformed' -T fields -e frame.number -e _ws.col.Info | jq -R -s -c 'split("\n") | map(select(length>0) | split("\t") | {frame: (.[0]|tonumber), info: .[1]})')
	expert=$(tshark -n $opts -r "$f" -Y '_ws.expert.severity >= 6291456' -T fields -e frame.number -e _ws.expert.message -e _ws.col.Protocol | jq -R -s -c 'split("\n") | map(select(length>0) | split("\t") | {frame: (.[0]|tonumber), message: .[1], protocol: .[2]})')
	printf '{"schemaVersion":"1.0","adapter":"tshark","version":"%s","frames":%s,"byProtocol":%s,"malformed":%s,"expert":%s}\n' \
		"$(tshark --version 2>/dev/null | head -1 | awk '{print $3}')" "$total" "$protos" "$malformed" "$expert"
	;;
*) printf '{"schemaVersion":"1.0","adapter":"tshark","implementation":"Wireshark tshark","license":"GPL-2.0-or-later","roles":["decoder"]}\n' ;;
esac
