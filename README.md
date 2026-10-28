# profinet-interop - PROFINET IO Reference Implementations in Containers

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Independent PROFINET IO implementations packaged as containers behind one
command-line contract, so that a PROFINET implementation under test can be
run against them on a real Layer 2 network: the IO-Device of rt-labs
**p-net** and of **pnio-rs**, the IO-Controller and DCP tool of
**profinet-py**, the DCP tool **pnio-dcp**, two MRP ring nodes, **umrp**
and Microchip's **mrp**, the SNMP manager of **Net-SNMP**, and two
independent decoders, **scapy** and **tshark**, that check every capture.

It serves [otfabric/go-profinet](https://github.com/otfabric/go-profinet),
whose interop tests (`make interop`) drive these images and write the
results the [interoperability matrix](docs/MATRIX.md) is generated from.

**Docs:** [CONTAINER_CONTRACT.md](docs/CONTAINER_CONTRACT.md) (the commands and JSON documents every image exposes) · [MATRIX.md](docs/MATRIX.md) (results) · [INTEROPERABILITY.md](docs/INTEROPERABILITY.md) (what each peer can and cannot test, the discrepancies found) · [versions.yaml](versions.yaml) (pins) · [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)

## The implementations

| Adapter | Implementation | Version | Licence | Role | go-profinet tested as |
|---------|----------------|---------|---------|------|-----------------------|
| `pnet` | [rt-labs p-net](https://github.com/rtlabs-com/p-net) | `ea5e554` (2023-11-10) | GPL-3.0-only or commercial | IO-Device (C) | IO-Controller, DCP requester, LLDP agent |
| `pnio-rs` | [pnio-rs](https://github.com/core-engineering/pnio-rs) | v0.1.0 | MIT OR Apache-2.0 | IO-Device (Rust) | IO-Controller, DCP requester |
| `profinet-py` | [profinet-py](https://github.com/f0rw4rd/profinet-py) | 0.6.6 | GPL-3.0-only or commercial | IO-Controller, DCP tool (Python) | IO-Device, DCP responder |
| `pnio-dcp` | [pnio-dcp](https://gitlab.com/pyshacks/pnio_dcp) | 1.2.0 | MIT | DCP tool (Python) | DCP responder |
| `scapy` | [scapy](https://scapy.net) contrib pnio | 2.6.1 | GPL-2.0-only | decoder | every capture |
| `tshark` | Wireshark tshark | 4.0.17 (Debian) | GPL-2.0-or-later | decoder | every capture |
| `netsnmp` | [Net-SNMP](https://www.net-snmp.org) command-line manager | 5.9.3 (Debian) | BSD-style | SNMP manager (C) | SNMP agent of the IO-Device |
| `umrp` | [umrp](https://github.com/giometti/umrp) with this repository's bridge ifdriver | v4.0 | GPL-2.0 | MRP ring node, MRM, MRC or MRA (C, user space); any Linux kernel | MRP manager, client and automatic manager in a ring |
| `mrp` | [microchip-ung/mrp](https://github.com/microchip-ung/mrp), unmodified | `177717e` (after v1.2) | GPL-2.0 | MRP ring node, MRM, MRC or MRA (C, on the kernel's bridge MRP); needs a host kernel with `CONFIG_BRIDGE_MRP` and without `CONFIG_NET_SWITCHDEV` (Docker Desktop: no bridge MRP; GitHub-hosted runners: switchdev built in, so the kernel refuses it: not applicable on either) | MRP manager and client in a ring |

Evaluated and not used: **profinet-python** (M256-Automation; no licence, a
Connect that compliant devices reject, unmaintained) and the **PI
Community Stack** (PROFIBUS & PROFINET International members only, under an
agreement that excludes combination with copyleft code). See
[INTEROPERABILITY.md](docs/INTEROPERABILITY.md).

## Use

```bash
make images
```

builds every image as `profinet-interop-<adapter>:dev`; the go-profinet
interop tests use these names by default.

```bash
docker run --rm profinet-interop-pnet:dev print-capabilities
```

Each container needs `--cap-add NET_RAW --cap-add NET_ADMIN` and, except
the MRP ring nodes (cabled with veth pairs, see the contract), a Docker
bridge network:

```bash
docker network create --subnet 10.77.0.0/24 pn
docker run -d --name pnet --network pn --ip 10.77.0.10 --cap-add NET_RAW --cap-add NET_ADMIN profinet-interop-pnet:dev device --station pnet-dut
docker run --rm --network pn --ip 10.77.0.4 --cap-add NET_RAW --cap-add NET_ADMIN profinet-interop-pnio-dcp:dev dcp identify-all
```

## Upstream candidates

A weekly workflow (`.github/workflows/candidate.yml`, also on demand)
compares every pin with the latest upstream: p-net with its newest GPL
release tag (later p-net trees are evaluation snapshots without ports:
reported and flagged), pnio-rs with its newest GitHub release, profinet-py,
pnio-dcp and scapy with PyPI, tshark and netsnmp with the Debian bookworm package. Where
a pin is behind, it builds the adapter on the latest upstream and checks it
with the smoke test, its capability document and the contract against the
other adapters at their pins (there is no cross-stack self-test here;
go-profinet's interop suite is the behavioural test). The decision table
goes to the Job Summary and to one issue that stays open while any pin is
behind. Pins are never moved automatically and no image is pushed.

```bash
make latest-upstream                                   # the decision table
make images
make candidate-scapy CANDIDATE_VERSION=2.8.0           # a release pin
make candidate-pnio-rs CANDIDATE_VERSION=<tag> CANDIDATE_SHA=<commit>
```

Every Dockerfile takes its upstream as `UPSTREAM_VERSION` and/or
`UPSTREAM_SHA` (`UPSTREAM_SHA256` for the pnio-dcp wheel). At the pin the
release build and its hash checks are unchanged; any other value takes a
candidate path that says `candidate build: ...` on stderr.

## Licences

The adapters, scripts and documents of this repository are MIT licensed.
The implementations keep their licences; none of their code is in this
repository. The images fetch them by pinned commit or version (and hash)
at build time and carry their licence under `/licenses/`. Images of GPL
implementations are built locally and are not published, so that each user
obtains the implementation from its source under its licence. The p-net
tree used is the last complete public GPLv3 snapshot, older than the
v1.0.2 security fixes: run it only on isolated test networks.

## Releases

Tags `vX.Y.Z` are released by `.github/workflows/release.yml` from the
notes in [RELEASE.md](RELEASE.md): it checks that the tag, `versions.yaml`
and the notes agree, builds and contract-checks every image on amd64 and
arm64, and publishes the notes with `versions.yaml` and the matrix results.
No image is published (see Licences). go-profinet pins a release
(`INTEROP_REF`).

## Project structure

```text
adapters/<name>/      Dockerfile and the adapter script of each implementation
docs/                 container contract, interoperability notes, matrix
matrix/results.json   the machine-readable matrix
scripts/              version check, latest upstream, matrix generation, release notes
versions.yaml         every pin, and the version of this repository
RELEASE.md            how a release is made; the notes of every version
```
