#!/bin/sh
# profinet-interop adapter for mrp (microchip-ung/mrp): one MRP ring node on
# the kernel's bridge MRP support. See docs/CONTAINER_CONTRACT.md.
#
#   profinet-interop node --role mrm|mrc|mra [--prio N] [--pport IF] [--sport IF] [--recv 200|500] [--ring-nr N]
#       waits for both ring ports (the harness moves veth ends into the
#       container), bridges them (br0), starts mrp_server and prints one
#       JSON event per line: start, ready, ring (state changes), until
#       SIGTERM; "unsupported" and exit 3 when the kernel has no bridge MRP
#   profinet-interop status       ring state, port states, probe frames received
#                                 and port counters (JSON); flushes are not
#                                 observable (the kernel flushes): -1
#   profinet-interop kernel-mrp   exit 0 when the kernel has bridge MRP support
#   profinet-interop print-capabilities | version
set -eu
RUN=/run/profinet-interop
mkdir -p "$RUN"
cmd=${1:-node}
[ $# -gt 0 ] && shift

ring_state() {
	mrp getmrp 2>/dev/null | sed -nE 's/.*ring_state: ([A-Z_0-9]+).*/\1/p' | head -n1
}

# ring_role: the role the daemon acts in (MRM or MRC; an MRA is either).
ring_role() {
	mrp getmrp 2>/dev/null | sed -nE 's/.*ring_role: ([A-Za-z]+).*/\1/p' | head -n1
}

counter() {
	cat "/sys/class/net/$1/statistics/$2" 2>/dev/null || echo 0
}

port_json() {
	state=$(bridge -o link show dev "$1" 2>/dev/null | sed -nE 's/.* state ([a-z]+) .*/\1/p' | head -n1)
	[ "$state" = blocking ] && state=blocked
	oper=$(cat "/sys/class/net/$1/operstate" 2>/dev/null || echo absent)
	printf '{"name":"%s","state":"%s","oper":"%s","rxPackets":%s,"txPackets":%s,"rxDropped":%s}' \
		"$1" "${state:-none}" "$oper" "$(counter "$1" rx_packets)" "$(counter "$1" tx_packets)" "$(counter "$1" rx_dropped)"
}

# kernel_mrp: whether this kernel's bridge takes an MRP instance: a test
# instance (ring 99) on a test bridge over a veth pair, through a running
# mrp_server.
kernel_mrp() {
	ip link add mrpk0 type bridge 2>/dev/null || return 1
	ok=1
	if ip link add mrpk1 type veth peer name mrpk2 2>/dev/null; then
		ip link set mrpk1 master mrpk0 && ip link set mrpk2 master mrpk0 &&
			ip link set mrpk0 up && ip link set mrpk1 up && ip link set mrpk2 up &&
			mrp addmrp bridge mrpk0 ring_nr 99 pport mrpk1 sport mrpk2 ring_role mrc >"$RUN/kernel-mrp.out" 2>&1 &&
			mrp getmrp 2>/dev/null | grep -q "ring_nr: 99" && ok=0
		if [ $ok -ne 0 ]; then
			# Why, for the caller's log.
			{ echo "kernel $(uname -r): mrp addmrp:"; cat "$RUN/kernel-mrp.out"; mrp getmrp; tail -n 20 "$RUN/mrp.log"; } >&2 2>/dev/null || true
		fi
		mrp delmrp bridge mrpk0 ring_nr 99 >/dev/null 2>&1 || true
		ip link del mrpk1 2>/dev/null || true
	fi
	ip link del mrpk0 2>/dev/null || true
	return $ok
}

# start_server starts mrp_server and waits for it.
start_server() {
	mrp_server -l 3 >"$RUN/mrp.log" 2>&1 &
	server=$!
	i=0
	until mrp getmrp >/dev/null 2>&1; do
		i=$((i + 1))
		[ $i -gt 100 ] && { echo '{"event":"error","error":"mrp_server did not start"}'; exit 1; }
		sleep 0.1
	done
}

case "$cmd" in
version)
	echo "mrp $(cat /licenses/mrp/COMMIT) (kernel bridge MRP)"
	;;
print-capabilities)
	cat <<'JSON'
{"schemaVersion":"1.0","adapter":"mrp","implementation":"microchip-ung/mrp","version":"v1.2+","license":"GPL-2.0","roles":["mrp-node"],
 "features":{"mrm":true,"mrc":true,"mra":true,"interconnection":false,"recoveryProfiles":["200","500"],"kernelMRP":true,
   "requires":"a host kernel with CONFIG_BRIDGE_MRP"}}
JSON
	;;
kernel-mrp)
	start_server
	rc=0
	kernel_mrp || rc=1
	kill "$server" 2>/dev/null || true
	exit $rc
	;;
status)
	pport=$(cat "$RUN/pport" 2>/dev/null || echo ringA)
	sport=$(cat "$RUN/sport" 2>/dev/null || echo ringB)
	probes=$(nft list counter bridge mrp probes 2>/dev/null | sed -nE 's/.*packets ([0-9]+).*/\1/p' | head -n1)
	printf '{"ring":"%s","role":"%s","flushes":-1,"probes":%s,"ports":[%s,%s]}\n' \
		"$(ring_state)" "$(ring_role)" "${probes:-0}" "$(port_json "$pport")" "$(port_json "$sport")"
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
	printf '{"event":"start","adapter":"mrp","role":"%s","pport":"%s","sport":"%s","recv":"%s"}\n' "$role" "$pport" "$sport" "$recv"
	start_server
	trap 'kill $server 2>/dev/null; exit 0' TERM INT
	if ! kernel_mrp; then
		printf '{"event":"unsupported","reason":"the kernel has no bridge MRP support (CONFIG_BRIDGE_MRP)","kernel":"%s"}\n' "$(uname -r)"
		exit 3
	fi
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
	# The counter "probes" counts the probe frames (EtherType 0x88B5,
	# broadcast) this node receives through the bridge.
	nft -f - <<'NFT'
table bridge mrp {
	counter probes { }
	chain input {
		type filter hook input priority 0; policy accept;
		ether type 0x88b5 counter name probes
	}
}
NFT
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
