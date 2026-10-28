#!/bin/sh
# profinet-interop adapter for umrp: one MRP ring node. See
# docs/CONTAINER_CONTRACT.md.
#
#   profinet-interop node --role mrm|mrc|mra [--prio N] [--pport IF] [--sport IF] [--recv 200|500] [--ring-nr N]
#       waits for both ring ports (the harness moves veth ends into the
#       container), bridges them (br0), starts mrp_server and prints one
#       JSON event per line: start, ready, ring (state changes), until SIGTERM
#   profinet-interop status       ring role (what an MRA acts as) and state, port states, FDB
#                                 flushes, probe frames received and port counters (JSON)
#   profinet-interop print-capabilities | version
set -eu
RUN=/run/profinet-interop
mkdir -p "$RUN"
cmd=${1:-node}
[ $# -gt 0 ] && shift

# ring_state: the state umrp's mrp tool reports, or "none".
ring_state() {
	mrp getmrp 2>/dev/null | sed -nE 's/.*ring_state: ([A-Z_0-9]+).*/\1/p' | head -n1
}

# ring_role: the role umrp acts in (MRM or MRC; an MRA is either).
ring_role() {
	mrp getmrp 2>/dev/null | sed -nE 's/.*ring_role: ([A-Za-z]+).*/\1/p' | head -n1
}

# counter IF NAME: an interface statistic, 0 when the interface is gone.
counter() {
	cat "/sys/class/net/$1/statistics/$2" 2>/dev/null || echo 0
}

port_json() {
	state=$(cat "$RUN/state-$1" 2>/dev/null || echo none)
	oper=$(cat "/sys/class/net/$1/operstate" 2>/dev/null || echo absent)
	printf '{"name":"%s","state":"%s","oper":"%s","rxPackets":%s,"txPackets":%s,"rxDropped":%s}' \
		"$1" "$state" "$oper" "$(counter "$1" rx_packets)" "$(counter "$1" tx_packets)" "$(counter "$1" rx_dropped)"
}

case "$cmd" in
version)
	echo "umrp $(cat /licenses/umrp/COMMIT) (ifdriver bridge)"
	;;
print-capabilities)
	cat <<'JSON'
{"schemaVersion":"1.0","adapter":"umrp","implementation":"umrp","version":"v4.0","license":"GPL-2.0","roles":["mrp-node"],
 "features":{"mrm":true,"mrc":true,"mra":true,"interconnection":false,"recoveryProfiles":["200","500"],"kernelMRP":false,
   "ifdriver":"bridge (generic Linux bridge port states; this adapter's ifdriver_bridge.c)"}}
JSON
	;;
status)
	pport=$(cat "$RUN/pport" 2>/dev/null || echo ringA)
	sport=$(cat "$RUN/sport" 2>/dev/null || echo ringB)
	flushes=$(wc -l <"$RUN/flushes" 2>/dev/null || echo 0)
	fdb=$(bridge fdb show br br0 dynamic 2>/dev/null | grep -vc permanent || true)
	probes=$(nft list counter bridge mrp probes 2>/dev/null | sed -nE 's/.*packets ([0-9]+).*/\1/p' | head -n1)
	printf '{"ring":"%s","role":"%s","flushes":%s,"fdbDynamic":%s,"probes":%s,"ports":[%s,%s]}\n' \
		"$(ring_state)" "$(ring_role)" "$((flushes + 0))" "$((fdb + 0))" "${probes:-0}" "$(port_json "$pport")" "$(port_json "$sport")"
	;;
node)
	role=""
	pport=ringA
	sport=ringB
	recv=200
	ringnr=1
	prio=""
	while [ $# -gt 0 ]; do
		case "$1" in
		--role) role=$2; shift 2 ;;
		--pport) pport=$2; shift 2 ;;
		--sport) sport=$2; shift 2 ;;
		--recv) recv=$2; shift 2 ;;
		--ring-nr) ringnr=$2; shift 2 ;;
		--prio) prio=$2; shift 2 ;;
		*) echo "unknown flag $1" >&2; exit 2 ;;
		esac
	done
	case "$role" in
	mrm|mrc|mra) ;;
	*) echo "--role must be mrm, mrc or mra" >&2; exit 2 ;;
	esac
	echo "$pport" >"$RUN/pport"
	echo "$sport" >"$RUN/sport"
	: >"$RUN/flushes"
	printf '{"event":"start","adapter":"umrp","role":"%s","pport":"%s","sport":"%s","recv":"%s"}\n' "$role" "$pport" "$sport" "$recv"
	# The ring ports arrive from outside.
	i=0
	while [ ! -e "/sys/class/net/$pport" ] || [ ! -e "/sys/class/net/$sport" ]; do
		i=$((i + 1))
		[ $i -gt 600 ] && { echo '{"event":"error","error":"ring ports did not appear"}'; exit 1; }
		sleep 0.1
	done
	ip link add br0 type bridge stp_state 0
	ip link set "$pport" master br0
	ip link set "$sport" master br0
	ip link set br0 up
	ip link set "$pport" up
	ip link set "$sport" up
	# The ring port states of ifdriver_bridge.c: a port in @blocked neither
	# receives nor sends through the bridge. The counter "probes" counts
	# the probe frames (EtherType 0x88B5, broadcast) this node receives
	# through the bridge: a test sends a known number around the ring and
	# finds a loop (counted twice) or a hole (not counted). umrp forwards MRP frames
	# itself (01:15:4E:00:00:01..04); the bridge must not flood them too.
	nft -f - <<'NFT'
table bridge mrp {
	set blocked { type ifname; }
	counter probes { }
	chain forward {
		type filter hook forward priority 0; policy accept;
		ether daddr & ff:ff:ff:ff:ff:f0 == 01:15:4e:00:00:00 counter drop
		iifname @blocked counter drop
		oifname @blocked counter drop
	}
	chain input {
		type filter hook input priority 0; policy accept;
		iifname @blocked counter drop
		ether type 0x88b5 counter name probes
	}
	chain output {
		type filter hook output priority 0; policy accept;
		oifname @blocked counter drop
	}
}
NFT
	mrp_server -d >"$RUN/umrp.log" 2>&1 &
	server=$!
	# On SIGTERM the ring instance goes first, then the daemon and the
	# bridge: the kernel then tears down no bridge with an MRP instance.
	trap 'mrp delmrp bridge br0 ring_nr "$ringnr" >/dev/null 2>&1; kill $server 2>/dev/null; ip link del br0 2>/dev/null; exit 0' TERM INT
	i=0
	until mrp getmrp >/dev/null 2>&1; do
		i=$((i + 1))
		[ $i -gt 100 ] && { echo '{"event":"error","error":"mrp_server did not start"}'; exit 1; }
		sleep 0.1
	done
	mrp addmrp bridge br0 ring_nr "$ringnr" pport "$pport" sport "$sport" ring_role "$role" ring_recv "$recv" ${prio:+prio "$prio"}
	touch "$RUN/ready"
	printf '{"event":"ready","bridge":"br0"}\n'
	last=""
	while kill -0 "$server" 2>/dev/null; do
		s=$(ring_state)
		ro=$(ring_role)
		if [ "$ro/$s" != "$last" ]; then
			printf '{"event":"ring","role":"%s","state":"%s"}\n' "$ro" "${s:-none}"
			last="$ro/$s"
		fi
		sleep 0.05
	done
	echo '{"event":"exit"}'
	;;
*)
	echo "unknown command $cmd" >&2
	exit 2
	;;
esac
