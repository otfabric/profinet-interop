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

## The peers

### p-net (IO-Device)

The most complete device: DCP Identify, Get, Set (name, IP, Signal, reset),
LLDP, Connect in legacy (RT_CLASS_1) and advanced (RT_CLASS_2) startup,
parameter writes, Read/Write, I&M0-4, RealIdentificationData, diagnosis
records, process and diagnosis alarms (its button 2), Release.

- Builds only from the last complete public GPLv3 tree, older than the
  v1.0.2 security fixes; its Connect needs the veth speed check removed.
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

### scapy and tshark (decoders)

Every capture of the tests is decoded by both. They are independent of
each other and of go-profinet, and both have PROFINET dissectors for DCP,
RT, alarms and the PNIO RPC blocks.

## Evaluated and not used

| Candidate | Why not |
|-----------|---------|
| profinet-python (M256-Automation) | no licence; its Connect sends only an ARBlockReq as IOSAR and fails against compliant devices; unmaintained since 2021 |
| PI Community Stack | PROFIBUS & PROFINET International members only, under an agreement that forbids combining it with copyleft code: not usable in public CI |
| Commercial stacks and PLCs | not available here; the hardware qualification tier of go-profinet's test strategy |

Of the four implementations the brief named, three are usable (p-net,
profinet-py, pnio-rs); profinet-python is not. pnio-dcp is the fourth
independent implementation exercised, for DCP only, and scapy and tshark
are independent decoders, not stacks. There is no second independent
IO-Controller: go-profinet's IO-Device is tested by profinet-py alone (and
by go-profinet's own controller).
