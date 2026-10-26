# Container contract

Version: **1.0** (`contract_version` in [versions.yaml](../versions.yaml))

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
```

An unknown command or flag exits with status 2.

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

### `decode` and `check`

`decode` (scapy) reports the frames per kind (`dcp`, `rt`, `alarm`, `udp`,
…), the DCE/RPC packets per type and operation, and the frames of a PROFINET
kind that scapy could not decode into a structured layer (`undecoded`).
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
