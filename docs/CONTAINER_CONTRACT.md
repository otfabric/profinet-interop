# Container contract

Version: **1.1** (`contract_version` in [versions.yaml](../versions.yaml))

Every adapter image runs one reference implementation of PROFINET IO and
exposes it through the same entrypoint, `profinet-interop`, with the commands
of the roles it has. Consumers (the interop tests of
[go-profinet](https://github.com/otfabric/go-profinet/tree/main/interop))
depend on this document, not on an adapter's source. A change that breaks it
bumps the major version; an addition bumps the minor one. Documents carry
`schemaVersion` `"1.0"`.

## Image layout

| Item | Value |
|------|-------|
| Image | `profinet-interop-<adapter>` (local builds: `:dev`); see [versions.yaml](../versions.yaml) for which images may be published |
| Entrypoint | `/usr/local/bin/profinet-interop` |
| Capabilities | the container needs `CAP_NET_RAW` and `CAP_NET_ADMIN` (raw Ethernet sockets; DCP Set IP changes the interface address) |
| Interface | `eth0`, attached to a Docker bridge network with a static IPv4 address |
| Licences | `/licenses/<implementation>/` (the upstream licence and the pinned commit) |
| Runtime directory | `/run/profinet-interop/` (raw logs of the implementation, readiness file `ready`) |

Layer 2 traffic (DCP, RT, alarms on EtherType 0x8892) passes a Linux bridge
unchanged. LLDP (01:80:C2:00:00:0E) does not unless the bridge's
`group_fwd_mask` has bit 14 set; the go-profinet harness sets it from a
privileged container in the host's network namespace, and reports LLDP as
not applicable where that is impossible.

## Commands

```text
profinet-interop print-capabilities           # capability document (JSON)
profinet-interop version                      # one line: implementation and version
profinet-interop device [flags]               # IO-Device roles: run until SIGTERM
profinet-interop controller [flags]           # IO-Controller roles: one scenario, one report
profinet-interop dcp <operation> [flags]      # DCP tool roles: one operation, one report
profinet-interop decode FILE.pcap             # decoder roles (scapy)
profinet-interop check FILE.pcap              # decoder roles (tshark)
profinet-interop button2                      # pnet: press the sample application's button 2
profinet-interop print-gsdml                  # pnio-rs: the device's GSDML
profinet-interop node --role mrm|mrc [flags]  # MRP ring node roles (umrp, mrp): run until SIGTERM
profinet-interop status                       # MRP ring node roles: the node's state (JSON)
profinet-interop kernel-mrp                   # mrp: exit 0 when the kernel has bridge MRP support
profinet-interop snmp OP --host IP [flags] OID... # SNMP manager roles (netsnmp): one operation, one report
```

An unknown command or flag exits with status 2. `make contract` checks every
image against this: `version` prints one line, `print-capabilities` a
capability document of schema version 1.0 with the adapter's name and roles,
and an unknown command exits 2.

### `device`

| Flag | Default | Meaning |
|------|---------|---------|
| `--iface IF` | `eth0` | interface |
| `--station NAME` | implementation default | NameOfStation |

The device writes one JSON object per line on stdout. Every object has an
`event` member; the first is

```json
{"event":"start","adapter":"pnet","iface":"eth0","mac":"…","ip":"…","station":"…"}
```

The events after it are the implementation's own, derived from its log:

| Adapter | Events |
|---------|--------|
| `pnet` | `connect`, `prmend`, `appready-confirmed`, `cyclic-started`, `write` (`index`), `read` (`index`), `alarm-confirmed`, `alarm-ack-confirmed`, `process-alarm-sent`, `diagnosis-added`, `diagnosis-removed`, `signal`, `reset`, `release`, `closed`, `abort`, `plug-submodule` |
| `pnio-rs` | `ar-state` (`state`: `Idle`, `Data`, `Idle (abort: …)`), `rt-stats`, `verdict` |

Adapter-specific commands of the device role:

| Adapter | Command | Effect |
|---------|---------|--------|
| `pnet` | `button2` | presses the sample application's button 2, which steps through a process alarm, adding, updating and removing a diagnosis, and a logbook entry |
| `pnio-rs` | `print-gsdml` | writes the device's GSDML (pnio-rs's own sample file) to stdout |

### `controller` (profinet-py)

```text
profinet-interop controller --station NAME [--iface eth0] [--gsdml FILE]
        [--rr N] [--duration S] [--output SLOT:SUBSLOT:HEX]... [--read-input SLOT:SUBSLOT]...
```

Runs the scenario: DCP discovery, I&M0 to I&M4, an I&M1 write, a user record
write and read (slot 2, subslot 1, index 0x0010), ReadImplicit of I&M0, a
read of an unknown index, the ModuleDiffBlock, diagnosis, slot discovery and,
with `--gsdml`, a cyclic AR built from the GSDML file, setting the outputs
and reading the inputs. It prints one report:

```json
{"schemaVersion":"1.0","adapter":"profinet-py","version":"0.6.6","station":"…",
 "steps":[{"step":"discover","ok":true,"value":{…}},{"step":"read-im0","ok":true,"value":{…}},…],
 "alarms":[…]}
```

A step that fails has `"ok":false` and an `error`; the report itself is
always written and the exit status is 0 unless the command line is wrong.

### `dcp`

| Adapter | Operations |
|---------|------------|
| `profinet-py` | `identify`, `get --mac M`, `set-name NAME --mac M [--permanent]`, `set-ip IP MASK GW --mac M [--permanent]`, `signal --mac M`, `reset --mac M` |
| `pnio-dcp` | `identify-all [--timeout S]`, `identify --mac M`, `get-name --mac M`, `get-ip --mac M`, `set-name --mac M NAME [--temporary]`, `set-ip --mac M IP MASK GW [--temporary]`, `blink --mac M`, `reset --mac M` |

Each prints one JSON document with `ok` (or the steps of profinet-py), the
value read and, for a Set, the DCP block error `code` and its `message`.

### `node` and `status` (MRP ring nodes: umrp, mrp)

A ring node is a container started without a Docker network: the
consumer creates a veth pair for each cable of the ring and moves its ends
into the nodes' network namespaces (it needs a privileged container in
the host's PID and network namespaces). `node` waits for both ring ports,
bridges them (`br0`), starts the MRP daemon and runs until SIGTERM.

| Flag | Default | Meaning |
|------|---------|---------|
| `--role mrm\|mrc` | (required) | ring role: manager or client |
| `--pport IF`, `--sport IF` | `ringA`, `ringB` | primary and secondary ring port |
| `--recv 200\|500` | `200` | recovery profile (ms) |
| `--ring-nr N` | `1` | ring instance |

Events: `start`, `ready`, `ring` (`state`: the daemon's MRM or MRC state,
`CHK_RC` ring closed, `CHK_RO` ring open, `PT_IDLE`, `DE_IDLE`, …), `exit`;
the mrp adapter prints `unsupported` and exits 3 when the kernel has no
bridge MRP support. `status` prints

```json
{"ring":"CHK_RC","flushes":3,"probes":100,
 "ports":[{"name":"ringA","state":"forwarding","oper":"up","rxPackets":…,"txPackets":…,"rxDropped":…},…]}
```

`flushes` counts the FDB flushes of the MRP daemon (-1 where the kernel
does them and they cannot be observed), `probes` the probe frames
(EtherType 0x88B5, broadcast) the node's bridge delivered to the node: a
consumer sends a known number around the ring to find a loop (a probe
counted twice) or a hole (not counted).

### `snmp` (Net-SNMP)

```text
profinet-interop snmp get|getnext|bulkget|walk|bulkwalk --host IP [--port 161] [--community public]
        [--version 1|2c] [--timeout S] [--retries N] [--max-rep N] [--non-rep N] OID...
profinet-interop snmp set --host IP [flags] --set OID TYPE VALUE
```

Runs one Net-SNMP tool (snmpget, snmpgetnext, snmpbulkget, snmpwalk,
snmpbulkwalk, snmpset) with numeric OIDs and no MIB files, and prints

```json
{"schemaVersion":"1.0","adapter":"netsnmp","op":"get","exit":0,"ok":true,
 "varbinds":[{"oid":"1.3.6.1.2.1.1.5.0","type":"Hex-STRING","value":"64 75 74","hex":"647574"},…],
 "errorStatus":"noSuchName","failedObject":"…","timeout":true}
```

`type` is Net-SNMP's name of the type it decoded (`INTEGER`, `Hex-STRING`,
`OID`, `Timeticks` with `value` the hundredths, `Counter32`, `Counter64`,
`Gauge32`, `IpAddress`, …) or the exception it reported (`noSuchObject`,
`noSuchInstance`, `endOfMibView`); octet strings carry `hex`.
`errorStatus` and `failedObject` are those of an error response
(`noSuchName`, `notWritable`, `tooBig`, …), `timeout` that no answer came;
`ok` is true when the tool succeeded without either.

### `decode` and `check`

`decode` (scapy) reports the frames per kind (`dcp`, `rt`, `alarm`, `mrp`,
`ptcp`, `udp`, …), the DCE/RPC packets per type and operation, the frames
of a PROFINET kind that scapy could not decode into a structured layer
(`undecoded`), and (since 1.1) the frames of a kind scapy has no dissector
for, MRP and PTCP, read but not decoded (`notDissected`,
`notDissectedCount`): those are a limit of the decoder, not evidence.
`check` (tshark) reports the frames per protocol, the malformed frames and
the expert infos of severity warning or error.

## `print-capabilities`

```json
{"schemaVersion":"1.0","adapter":"pnet","implementation":"p-net","version":"…","license":"GPL-3.0-only",
 "roles":["device"],"features":{"dcpIdentify":true,"lldp":true,"connect":true,…}}
```

`features` says what the implementation supports, so that a consumer can
tell a failing test from a feature the peer does not have. The feature
names follow the tables of [MATRIX.md](MATRIX.md).

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | the command ran; failures of steps are in the report |
| 1 | the implementation failed to start |
| 2 | usage error: unknown command, flag or operation |
| 3 | the host does not support the implementation (mrp: no bridge MRP in the kernel) |
