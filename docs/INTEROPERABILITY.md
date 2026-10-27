# Interoperability notes

What each reference implementation can test, how go-profinet is exercised
against it, and the discrepancies the tests found. The results themselves
are in [MATRIX.md](MATRIX.md); reproduce them with `make interop` in
go-profinet after `make images` here.

## Test topology

Every test creates a Docker bridge network with a /24 subnet. The reference
implementation runs in one container, go-profinet's `otfnode` (the
controller, device, DCP and LLDP roles of go-profinet over its AF_PACKET
backend and the kernel's UDP stack) in another, both with `CAP_NET_RAW` and
`CAP_NET_ADMIN`. Tool containers get a fixed MAC address per test host
(p-net ignores a second DCP requester for 3 s after a Get or Set, which a
fresh MAC per operation would trigger). A tcpdump sidecar in the network
namespace of the peer captures the exchange; scapy and tshark decode the
capture, and a test fails on a frame either cannot decode or flags.

LLDP needs the bridge to forward 01:80:C2:00:00:0E: the harness sets bit
14 of the bridge's `group_fwd_mask` from a privileged container in the
host's network namespace, and reports LLDP as not applicable where it
cannot.

MRP rings are cabled differently: three containers without a Docker
network (go-profinet's `otfnode mrp` and two nodes of umrp or mrp), each
cable a veth pair whose ends a privileged helper (host PID and network
namespaces) moves into two nodes. Taking one end down breaks the cable: both
ends lose their link, as a pulled cable does. tcpdump captures the MRP
frames (EtherType 0x88E3) on one of go-profinet's ring ports.

## The peers

### p-net (IO-Device)

The most complete device: DCP Identify, Get, Set (name, IP, Signal, reset),
LLDP, Connect in legacy (RT_CLASS_1) and advanced (RT_CLASS_2) startup,
parameter writes, Read/Write, I&M0-4, RealIdentificationData, diagnosis
records, process and diagnosis alarms (its button 2), Release.

- Builds only from the last complete public GPLv3 tree, older than the
  v1.0.2 security fixes; its Connect needs the veth speed check removed.
- Plugs any module the controller expects (logs it as "unknown") instead
  of reporting it in a ModuleDiffBlock: a wrong configuration cannot be
  detected against p-net (tested as such).
- Sends its WriteMultiple answer with the IODWriteResHeader of the
  WriteMultiple first (go-profinet's device now does the same).
- Answers an unknown record index with `DE 80 A0 00` (application read
  error) rather than `B0` (invalid index).
- Does not answer DCP Get with the AllSelector; go-profinet asks for the
  identity blocks by name.
- **Ties an AR to the RPC activity of its Connect.** A PrmEnd on another
  activity is acknowledged but never raises PRMEND, so ApplicationReady
  never follows (found by these tests; go-profinet now makes every call of
  an AR on the activity of its Connect).
- Starts its input provider only after PrmEnd: a controller watchdog that
  runs from Connect expires (found by these tests; go-profinet's consumer
  watchdog now starts with the first frame or when the AR is established).
- Numbers its first alarm DATA PDU 0xFFFF, then 0, 1, ... (found by these
  tests together with pnio-rs and profinet-py; go-profinet first expected 0
  and NACKed the alarm until p-net aborted the AR).
- Does not process DCE/RPC ACK packets ("Unknown packet_type 7"); go-profinet
  marks its PNIO calls idempotent, as controllers do, and sends none.

### pnio-rs (IO-Device)

A single-AR IO-Device with a fixed sample model, described by its own GSDML,
from which go-profinet derives the expected configuration
(`gsdml.ToModel`).

- Accepts FrameIDs 0x8000-0xBBFF only, so a controller must use advanced
  startup with RTClass 2; a legacy RT_CLASS_1 Connect is rejected (tested as
  such).
- No DCP Get, Set name, Signal or Reset; no LLDP; no ModuleDiffBlock (a
  mismatch rejects Connect); no diagnosis records or I&M4 (invalid index);
  low-priority diagnosis alarms only.
- Agrees with go-profinet and p-net on the 56-octet I&M1 record.

### profinet-py (IO-Controller, DCP tool)

The only independent open-source IO-Controller: it tests go-profinet's
IO-Device, including an IOSAR (device access AR) for its acyclic requests
and a cyclic IOCAR configured from the GSDML go-profinet generates.

- Writes I&M1 with BlockLength 58 and two padding octets after the block
  header; p-net, pnio-rs and go-profinet use BlockLength 56. go-profinet's
  device rejects the write with `DF 80 B8 00` instead of storing shifted
  text. Recorded as a profinet-py deviation.
- `read_all_diagnosis` reads index 0xF000 (RealIdentificationData) and
  decodes it as diagnosis data; the entries it reports are artefacts.
- Cyclic exchange in Python is reliable at 32 ms and above (its own note).

### pnio-dcp (DCP tool)

Identify all, Get name and IP, Set name and IP (temporary and permanent),
blink (Signal) and reset against go-profinet's DCP responder.

### umrp (MRP ring node)

giometti/umrp runs the MRP state machine (IEC 62439-2 as its author read
it) in user space: it sends MRP_Test, TopologyChange and LinkChange frames,
receives and forwards MRP frames on raw sockets, and drives the ring port
states through an `ifdriver`. Upstream's drivers need the kernel's bridge
MRP support (netlink) or a vendor switch tool; this adapter adds
`ifdriver_bridge.c`, which puts a blocked port into an nftables set whose
rules drop every frame the Linux bridge would receive from or send to it,
and flushes the bridge's FDB with iproute2. (The bridge's own port states
cannot be used: without STP the kernel makes every port forwarding again,
and user-space STP is not available in a network namespace.) So umrp runs
on any kernel, Docker Desktop's included; the state machine, the frames and
the forwarding decisions are umrp's, the port blocking is the adapter's.

What it tests in go-profinet: the manager against two umrp clients (ring
closed with the secondary port blocked, test frames through foreign
clients, ring open on a break between them, the clients' FDB flush on
go-profinet's TopologyChange) and a client next to a umrp manager (link
change frames, TopologyChange received), each with probe frames counted
at every umrp node for loops and holes, a measured outage and seeded cable
faults.

### mrp (MRP ring node on the kernel)

microchip-ung/mrp, Microchip's daemon for the Linux bridge's MRP support
(`CONFIG_BRIDGE_MRP`, Linux 5.8 and later), built unmodified: the kernel
sends the test frames, forwards MRP frames and sets the port states, the
daemon runs the state machine. It needs a host kernel with bridge MRP: the
Ubuntu kernels of the GitHub-hosted runners have it; Docker Desktop's
linuxkit kernel has not, so there the tests are not applicable (the node
prints `unsupported` and exits 3). The same tests as with umrp run against
it, except the FDB flush count, which the kernel does unobservably.

### scapy and tshark (decoders)

Every capture of the tests is decoded by both. They are independent of
each other and of go-profinet, and both have PROFINET dissectors for DCP,
RT, alarms and the PNIO RPC blocks. scapy has none for MRP and PTCP: it
reads those frames without decoding them, and since contract 1.1 reports
them as `notDissected` (go-profinet records a decoder limit, not a pass);
tshark decodes MRP (PN-MRP) and PTCP. tshark runs its heuristic dissectors
before the port-based ones, so that RPC on an ephemeral port that another
protocol registered (UDP 37008, TZSP) is still decoded as DCE/RPC.

## Evaluated and not used

| Candidate | Why not |
|-----------|---------|
| profinet-python (M256-Automation) | no licence; its Connect sends only an ARBlockReq as IOSAR and fails against compliant devices; unmaintained since 2021 |
| PI Community Stack | PROFIBUS & PROFINET International members only, under an agreement that forbids combining it with copyleft code: not usable in public CI |
| Commercial stacks and PLCs | not available here; the hardware qualification tier of go-profinet's test strategy |
| Linux kernel MRP with iproute2 alone | iproute2 has no `bridge mrp` command (the netlink API exists, its iproute2 patch was never merged); microchip-ung/mrp is the user-space side of it |

Of the four implementations the brief named, three are usable (p-net,
profinet-py, pnio-rs); profinet-python is not. pnio-dcp is the fourth
independent implementation exercised, for DCP only, and scapy and tshark
are independent decoders, not stacks. There is no second independent
IO-Controller: go-profinet's IO-Device is tested by profinet-py alone (and
by go-profinet's own controller).
