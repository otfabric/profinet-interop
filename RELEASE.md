# profinet-interop Releases

## How a release is made

1. Write the notes of the version below and set `interop_version` in
   `versions.yaml` to it, in the same change. CI fails when RELEASE.md has
   no notes for the version `versions.yaml` names.
2. CI is green on the commit to release; when the matrix changed, it is
   regenerated from go-profinet's Interop workflow (`make matrix
   RESULTS=dir SUT_VERSION=<go-profinet version>`).
3. Tag `vX.Y.Z` and push the tag. The release workflow
   (`.github/workflows/release.yml`) checks that the tag, `versions.yaml`
   and the notes agree, builds every image on amd64 and arm64 and checks it
   against the contract, then publishes the GitHub release with
   `versions.yaml`, the matrix results and their checksums. **No reference
   image is published**: p-net, profinet-py, umrp, mrp, Scapy and tshark are GPL, and every
   user builds the images from upstream (`make images`). OT Fabric's own image,
   `profinet-interop-otfabric`, is not part of a release: the **Own stack
   (go-profinet)** workflow publishes it by hand (own/go-profinet/README.md).
4. go-profinet pins the tag (`INTEROP_REF` in its Makefile and Interop
   workflow).

The notes are the body of the GitHub release: everything after the heading
`## vX.Y.Z` up to the next line that is exactly `---`
(`scripts/release-notes.sh vX.Y.Z` prints it). This is the format of every
otfabric repository and the rule of the shared release workflow, so: one
section per version, newest first, each ending with a `---` line, and no
`---` line inside a section.

Tags are immutable. A fix is a new version.

| What changed | Version |
|--------------|---------|
| Contract changed incompatibly | major |
| New adapter, operation, capability or matrix feature | minor |
| Upstream pin, base image, matrix regeneration or bug fix with unchanged contract | patch |

---

## v0.10.0

**Date:** 2026-11-23
**Previous release:** v0.9.2

## Summary

A GSDML corpus: a manifest of 191 public GSDML files and archives and a
tool that downloads them into a local cache (docs/CORPUS.md); no vendor
file is committed or published. Contract 1.4: tshark's `fields` command
reports the values it decodes, so that a consumer can check what a frame
says, not only that it is well formed. Stable IDs for go-profinet's
APIData (index 0xF821) checks. The tshark image changes (the adapter
script); the other images are unchanged.

## Changes

### Added

- **`corpus/manifest.jsonl`**: 132 artifacts in 32 GitHub repositories
  (130 GSDML files, 2 zip archives), each pinned to a commit and verified
  by its git blob ID, and 59 open vendor downloads (58 zip archives),
  verified by a SHA-256 recorded on the first fetch: 58 have one, the
  Universal Robots file (`vendor-43e8ff6206bb`) none, its URL answered 403.
- **`corpus-fetch`** (`make corpus-fetch`, Go standard library only):
  downloads into `$XDG_CACHE_HOME/otfabric/gsdml-corpus`, verifies every
  artifact, extracts the GSDML members of archives with path and size
  limits, and writes `index.jsonl`; `-record` records the hashes of entries
  that have none. Nothing runs it implicitly.
- CI: the tool's tests (offline) and a check that no GSDML file is
  committed outside `adapters/`.
- **Contract 1.4, `profinet-interop fields FILE.pcap FILTER FIELD...`**
  (tshark): per frame that matches the display filter, every occurrence
  of each field as tshark decodes it (docs/CONTAINER_CONTRACT.md). A
  filter or field tshark does not know exits 2; `make contract` checks
  that `fields` without arguments exits 2. A compatible addition.
- **Stable IDs** (matrix/ids.tsv) for go-profinet's checks of APIData
  (0xF821): p-net's answer outside and inside an AR
  (`pnetcontroller.apidata-0xf821-by-readimplicit-decoded`,
  `pnetcontroller.apidata-0xf821-in-the-ar-decoded`), and the APIs tshark
  decodes from a two-API APIData block
  (`codecdecoders.tshark-fields-codecs-pcap-apidata-apis`).

### Not changed

- The committed matrix (docs/MATRIX.md, matrix/results.json) is still the
  one from go-profinet v0.8.1; it does not hold the new checks.

---

## v0.9.2

**Date:** 2026-11-22
**Previous release:** v0.9.1

## Summary

Pins moved to the latest upstream: scapy 2.8.0, and new digests for the
`debian:trixie-slim` and `golang:1.27.2-trixie` base images of the
`profinet-interop-otfabric` image. Contract 1.3 is unchanged.

## Changes

### Changed

- **`scapy`**: 2.6.1 → 2.8.0 (PyPI).
  - The PROFINET contrib layers it uses are the same: `pnio.py` is
    unchanged, and `pnio_dcp.py` only drops a `compat.orb` call.
  - Both known differences still hold: no MRP dissector, and no DCP DHCP
    block class.
  - Their evidence links in `tests/known-differences.tsv` now point at
    2.8.0 (`e2e35c0`).
- **Base images of `own/go-profinet`**: `debian:trixie-slim` →
  `sha256:a72b4433de1c…` and `golang:1.27.2-trixie` →
  `sha256:476679348749…`. These are the same tags at new digests, and
  `versions.yaml` `base_images` matches.

---

## v0.9.1

**Date:** 2026-11-22
**Previous release:** v0.9.0

## Summary

The `mrp` image (microchip-ung/mrp) is built with one fix. The fix is
proposed upstream in https://github.com/microchip-ung/mrp/pull/4. Contract
1.3 and every other adapter are unchanged.

## Changes

### Fixed

- **`mrp`**: an MRA that gave way to a better manager could stay an MRC
  with its secondary port blocked, which leaves a hole in the ring.
  - The cause is in `mrp_port_ring_open` in `state_machine.c`. When the
    kernel reported one ring port's MRP_Test frames lost or back, the node
    ran the MRM state machine even in the MRC role. From `CHK_RO`, that
    blocked the port while the MRC state stayed `PT_IDLE`.
  - go-profinet's TestMRPAuto failed on it intermittently.
  - The image now applies commit `ee224a1` of
    https://github.com/boeboe/mrp on top of the upstream pin `177717e`. The
    patch is in the image at `/licenses/mrp/fix.patch`.
  - `version` and `print-capabilities` name the fix.
  - The fix is to be dropped when upstream has it.

---

## v0.9.0

**Date:** 2026-11-15
**Previous release:** v0.8.0

## Summary

A schema for the capability document, the system under test in the matrix
results, and the cross-stack self-test and a base-image check in CI. Contract
1.3 and every adapter are unchanged.

## Changes

### Added

- **`schemas/capabilities.schema.json`**: the capability document of
  `print-capabilities` (docs/CONTAINER_CONTRACT.md) as JSON Schema 2020-12:
  the required fields, the six roles, every feature name with its type, and
  `upstream`. `scripts/check-capabilities.py ADAPTER [FILE]` checks a
  document against it; `make contract` now uses it for every image (and needs
  the `jsonschema` package), and the **Own stack (go-profinet)** workflow
  checks the otfabric image with it. Every adapter's document is valid.
- `make matrix` takes `SUT_VERSION=<go-profinet version>` (required) and
  `SUT_REVISION=<commit>`; `matrix/results.json` records them as `sut`.

### Changed

- `matrix/interop-result-v1.json` names the go-profinet that produced the
  matrix (v0.8.1, commit 8822e05) instead of `unrecorded`; the results and
  the verdict are unchanged (248 pass, 6 unsupported, 14 known-difference).
  `matrix-to-results.py` stops when `results.json` has no `sut`.
- CI runs the cross-stack self-test (`make interop`) on amd64 and arm64 after
  the contract and checks `reports/results.json` with `interop_result.py`; the
  documents are uploaded. The candidate check runs it too for an adapter of
  `INTEROP_ADAPTERS` (pnio-dcp, pnio-rs).
- The upstream probe (`candidate.yml`) runs daily instead of weekly, and
  compares every pinned base image with the digest its tag points to now
  (otfabric/.github `upstream-images` and `upstream-report` v3.8.0, issue
  "Upstream base images: digests behind their tags").
- The workflows install `jsonschema==4.26.0` instead of the newest jsonschema.
- `own/go-profinet` builds against go-profinet v0.10.0 (go.mod), and its
  `OnAlarm` handler no longer blocks once 64 alarms are pending with no
  `--wait-alarms` reader: go-profinet calls it before the alarm is
  acknowledged and requires it not to block. The image is published by hand,
  outside this release.
- SECURITY.md names the one published image, OT Fabric's own, and the
  advisories that apply to it.

---

## v0.8.0

**Date:** 2026-11-06
**Previous release:** v0.7.1

## Summary

OT Fabric's own stack behind the contract, and a small cross-stack self-test
(otfabric/engineering ADR-0012).

## Changes

### Added

- **`own/go-profinet/`**: `ghcr.io/otfabric/profinet-interop-otfabric`, go-profinet behind the container contract (adapter `otfabric`: IO-Device, IO-Controller, DCP tool), so that other PROFINET stacks can test against ours. Not an independent implementation (`upstream.independentEngine: false`) and not part of a release: the manual **Own stack (go-profinet)** workflow builds it from the latest go-profinet release, tests it on amd64 and arm64 with the scripts of the latest harness release against references built from that release, and publishes `:<go-profinet version>` and `:latest` from `main`. It is the only image this repository publishes.
- **Cross-stack self-test**, `scripts/interop.sh <adapter>...` (`make interop`): DCP Identify, Get and Set NameOfStation of every DCP tool against every IO-Device, and Connect, cyclic data and I&M0 of every IO-Controller against every IO-Device, each pair on its own Docker bridge network (`tests/cases.tsv`), with `reports/results.json` as interop-result-v1; `GATE=<adapter>` runs only the pairs that involve it. Drivers for otfabric, pnio-dcp, profinet-py, pnio-rs and pnet (DCP only). MRP, decoders and SNMP stay with go-profinet's interop suite, the behavioural test.
- `scripts/lib.sh` (`image_of`: `ADAPTER_IMAGE_<adapter>` overrides an image), `scripts/smoke.sh <adapter>...`, `scripts/retry.sh`; `scripts/check-contract.sh [TAG] [adapter...]`.

### Changed

- **Contract 1.3**: the capability document has an `upstream` object (`name`, `version`, optional `revision`, `independentEngine`); every adapter declares it, `make contract` checks it. A compatible addition.
- `matrix-to-results.py` records the otfabric image as `independent: false`.

---

## v0.7.1

**Date:** 2026-10-31
**Previous release:** v0.7.0

### Changed

- Policy 1.2: build output in `bin/` and `release/`, and shared CI at v3.3.0.

---

## v0.7.0

**Date:** 2026-10-30

**Previous release:** v0.6.0

## Summary

The matrix as the organisation's interop-result-v1.

## Changes

### Added

- **`matrix/interop-result-v1.json`** ([interop-result-v1](schemas/interop-result-v1.schema.json)): `make matrix` writes it next to `matrix/results.json`, which keeps its shape, and the release attaches it. Stable IDs: `matrix/ids.tsv`. `peer-deviation` is `known-difference` with a waiver of `tests/known-differences.tsv`; without one it is a fail. `n/a` is `unsupported`. Only `pass` counts as passing; a run with no pass, or with a waiver that no longer reproduces, fails. Existing reports keep their shape.

---

## v0.6.0

**Date:** 2026-10-29
**Previous release:** v0.4.1

## Summary

Released together with go-profinet v0.6.0 and profinetctl v0.6.0: from
this version the three repositories share one version number (there is no
v0.5.x of profinet-interop). Contract 1.2 and every adapter are unchanged.
The matrix, regenerated from go-profinet v0.6.0's Interop and Kernel MRP
workflows: 40 test runs, 248 pass, 0 fail, 6 n/a, 14 attributed peer
deviations.

| Peer | pass | fail | n/a | peer deviation |
|------|-----:|-----:|----:|---------------:|
| p-net | 56 | 0 | 1 | 0 |
| pnio-rs | 13 | 0 | 3 | 0 |
| profinet-py | 32 | 0 | 1 | 3 |
| pnio-dcp | 8 | 0 | 0 | 0 |
| umrp | 32 | 0 | 0 | 2 |
| microchip-ung/mrp (kernel, micro-VM) | 31 | 0 | 1 | 0 |
| Net-SNMP | 29 | 0 | 0 | 0 |
| tshark, scapy (decoders) | 47 | 0 | 0 | 9 |

## Changes

- Matrix regenerated; go-profinet's MRA tests now run the 500 ms profile
  (`--recv 500`), which INTEROPERABILITY.md explains.

---

## v0.4.1

**Date:** 2026-10-28
**Previous release:** v0.4.0

## Summary

Documentation and metadata corrections; contract 1.2 unchanged. The
matrix: 39 test runs, 248 pass, 0 fail, 6 n/a, 14 attributed peer
deviations.

| Peer | pass | fail | n/a | peer deviation |
|------|-----:|-----:|----:|---------------:|
| p-net | 56 | 0 | 1 | 0 |
| pnio-rs | 13 | 0 | 3 | 0 |
| profinet-py | 32 | 0 | 1 | 3 |
| pnio-dcp | 8 | 0 | 0 | 0 |
| umrp | 32 | 0 | 0 | 2 |
| microchip-ung/mrp (kernel, micro-VM) | 31 | 0 | 1 | 0 |
| Net-SNMP | 29 | 0 | 0 | 0 |
| tshark, scapy (decoders) | 47 | 0 | 0 | 9 |

## Changes

- `versions.yaml`: `published` says what this project publishes (no
  image), the new `publishable` what the licences would allow;
  THIRD_PARTY_NOTICES.md says the same. The mrp entry names go-profinet's
  Kernel MRP micro-VMs.
- Capabilities: umrp's ifdriver is described as what it is (an nftables
  set of blocked ports); mrp requires a kernel without
  `CONFIG_NET_SWITCHDEV` as well.
- Contract text: the ring nodes' `error` and `unsupported` events, their
  SIGTERM cleanup, umrp's `fdbDynamic`, pnio-rs's `--diag`, profinet-py's
  `--timeout`, and the ring nodes' interfaces.
- Matrix: one go-profinet role for Net-SNMP.

---

## v0.4.0

**Date:** 2026-10-28
**Previous release:** v0.3.0

## Summary

The MRP automatic manager (MRA) on both ring node adapters, so that
go-profinet's MRA is tested against umrp's and the kernel's; contract 1.2;
and the first matrix with microchip-ung/mrp on the kernel's bridge MRP
(Linux 6.12 without switchdev, in go-profinet's Kernel MRP micro-VM
workflow): 31 pass, 0 fail, 1 n/a (the FDB flush the kernel does).

## Changes

- Contract 1.2 (additions only): `node --role mra` and `--prio N` for the
  MRP ring nodes (umrp, mrp); `status` and the `ring` events report `role`,
  what the node acts as (`MRM` or `MRC`).
- `umrp` and `mrp`: capability `mra` true.
- Ring nodes delete their MRP instance and bridge on SIGTERM.
- Matrix regenerated: go-profinet's Interop workflow against this release
  plus its Kernel MRP workflow for the mrp rows.
- Documented the kernel's overlong MRA option and the namespace teardown
  hang seen in the micro-VM (docs/INTEROPERABILITY.md).
- Documented umrp's MRA deviation: as a client it keeps reclaiming the
  manager role (its test monitor ignores the manager it gave way to), and
  its MRP_Options carry the OUI 00-00-00, which tshark does not decode.

---

## v0.3.0

**Date:** 2026-10-27
**Previous release:** v0.2.1

## Summary

Two independent MRP implementations as ring nodes, so that go-profinet's
MRP manager and client are tested against software that is not
go-profinet: **umrp** (giometti/umrp, user space, runs on any Linux
kernel) and **mrp** (microchip-ung/mrp, unmodified, on the kernel's
bridge MRP support where the host kernel has it); and **Net-SNMP**'s
manager for go-profinet's SNMP agent. Contract 1.1.

## Changes

- New adapter `umrp`: umrp v4.0 with `ifdriver_bridge.c` (GPL-2.0, this
  repository's only GPL file), which applies umrp's ring port states to a
  Linux bridge through an nftables set of blocked ports, so no kernel MRP
  support is needed. Commands `node` and `status` (ring state, port states,
  FDB flushes, probe frames received).
- New adapter `mrp`: microchip-ung/mrp `177717e` (after v1.2) with libcfm,
  unmodified; needs a host kernel with `CONFIG_BRIDGE_MRP` and, on a
  software bridge, without `CONFIG_NET_SWITCHDEV`. Neither Docker Desktop
  (no bridge MRP) nor the GitHub-hosted runners (switchdev built in: the
  kernel answers the MRP instance with EOPNOTSUPP) qualify, so its tests
  are not applicable there; `kernel-mrp` tells, `node` prints `unsupported`
  and exits 3. A kernel built without switchdev, in a VM, would run it.
- New adapter `netsnmp`: Net-SNMP's command-line manager (Debian bookworm
  package `snmp` 5.9.3), command `snmp get|getnext|bulkget|walk|bulkwalk|set`
  with a JSON report of what Net-SNMP decoded. Pinned by Debian like tshark.
- Contract 1.1 (additions only): profinet-py's `controller --reparam` (PrmBegin, writes, PrmEnd and ApplicationReady on the running AR), the SNMP manager role (`snmp`), the MRP ring node role (`node`, `status`,
  `kernel-mrp`, exit code 3), and scapy's `decode` reports the frames it
  has no dissector for (MRP, PTCP) as `notDissected`: they were counted as
  decoded before, which overstated scapy's evidence for MRP.
- `scripts/latest-upstream.py`, the candidate workflow and
  `scripts/check-versions.sh` cover both new adapters (umrp by tag, mrp by
  the head of its default branch).
- `scripts/matrix.py` takes go-profinet's role from a test's
  "(go-profinet: …)" role and lists every role of a peer.
- The matrix is regenerated from go-profinet's interop suite with the new
  tests (go-profinet's branches feat/mrp-interop, feat/netsnmp-interop and
  feat/reparameterize together), run on Docker Desktop (linuxkit 7.0.14,
  arm64): 33 test runs, 193 pass, 0 fail, 8 n/a (the kernel MRP peer, and
  re-parameterization that p-net and pnio-rs refuse), 8 attributed
  deviations (profinet-py's padded I&M1, decoder limits of scapy and
  Wireshark).

| Peer | pass | fail | n/a | peer-deviation |
|------|-----:|-----:|----:|---------------:|
| Net-SNMP | 29 | 0 | 0 | 0 |
| mrp (kernel) | 0 | 0 | 3 | 0 |
| p-net | 55 | 0 | 2 | 0 |
| pnio-dcp | 8 | 0 | 0 | 0 |
| pnio-rs | 13 | 0 | 3 | 0 |
| profinet-py | 29 | 0 | 0 | 3 |
| scapy | 16 | 0 | 0 | 3 |
| tshark | 15 | 0 | 0 | 0 |
| tshark/scapy | 8 | 0 | 0 | 2 |
| umrp | 20 | 0 | 0 | 0 |

---

## v0.2.1

**Date:** 2026-10-27
**Previous release:** v0.2.0

## Summary

The interoperability matrix, regenerated from go-profinet's interop suite
on its v0.3.0 code (main 8210d3d): 19 test runs, 126 pass, 0 fail, 2 n/a,
4 attributed peer deviations.

## Changes

- New decoder checks of go-profinet's frames: the SNMP agent (tshark and
  scapy decode every datagram of a walk), RT_CLASS_UDP frames and
  Connect, the DCP DHCP blocks, and the PROFINET MRP records.
- Two decoder deviations recorded, not failures of go-profinet: scapy has
  no DCP DHCP block class, and Wireshark decodes the data of DHCP options
  61 and 255 only.

| Peer | pass | fail | n/a | peer-deviation |
|------|-----:|-----:|----:|---------------:|
| p-net | 55 | 0 | 0 | 0 |
| pnio-rs | 12 | 0 | 2 | 0 |
| profinet-py | 22 | 0 | 0 | 2 |
| pnio-dcp | 8 | 0 | 0 | 0 |
| scapy | 11 (was 7) | 0 | 0 | 0 |
| tshark | 10 (was 7) | 0 | 0 | 0 |
| tshark and scapy | 8 (was 2) | 0 | 0 | 2 |

No change to the images, the adapters or any upstream pin.

---

## v0.2.0

**Date:** 2026-10-27
**Previous release:** v0.1.3

## Summary

A weekly check of every pin against the latest upstream, with candidate
builds of newer upstreams, as in the other otfabric interop repositories.

## Changes

- **Upstream candidates** workflow (`.github/workflows/candidate.yml`,
  weekly and on demand): `scripts/latest-upstream.py` compares each pin
  with the newest upstream: p-net with its newest GPL release tag (the
  head of its `public` branch and its `public/` releases are reported but
  flagged: evaluation snapshots without ports, not GPL-complete), pnio-rs
  with its newest GitHub release, profinet-py, pnio-dcp (with the wheel
  sha256) and scapy with PyPI, tshark with the Debian bookworm package
  (pinned by Debian: reported, never built as a candidate). Where a pin is
  behind, the adapter is built on the latest upstream and checked with the
  smoke test, its capability document and the contract against the other
  pins. The decision table goes to the Job Summary and to one issue that
  stays open while any pin is behind. Pins are never moved automatically
  and no image is pushed.
- **`make candidate-<adapter> CANDIDATE_VERSION=... CANDIDATE_SHA=...`**
  (`CANDIDATE_SHA256=...` for pnio-dcp) and **`make latest-upstream`**.
- Every Dockerfile names its upstream `UPSTREAM_VERSION` and/or
  `UPSTREAM_SHA` (`UPSTREAM_SHA256` for pnio-dcp), replacing
  `PNET_COMMIT`, `PNIO_RS_COMMIT`, `PROFINET_PY_VERSION`,
  `PNIO_DCP_VERSION`, `PNIO_DCP_SHA256` and `SCAPY_VERSION`. At the pin the
  build and its hash checks are unchanged; any other value takes a
  candidate path (says `candidate build: ...` on stderr, skips the pinned
  hash). `scripts/check-versions.sh` checks the new names and matches the
  whole `ARG` line.
- First run: scapy 2.6.1 is behind 2.8.0 (its candidate passes the smoke
  test, the capability document and the contract; the pin stays at 2.6.1
  until go-profinet's interop suite has run on it); every other pin is the
  latest (p-net flagged as above).

The images, the adapters, the contract (1.0), every upstream pin and the
matrix are unchanged from v0.1.3.

---

## v0.1.3

**Date:** 2026-10-27
**Previous release:** v0.1.2

## Summary

Releases are cut by a workflow from the notes in this file, as in every
otfabric repository.

## Changes

- **Release workflow** (`.github/workflows/release.yml`, on a pushed
  `vX.Y.Z` tag): checks that the tag, `interop_version` in `versions.yaml`
  and the notes in RELEASE.md agree; builds every adapter image on amd64
  and arm64 and checks it against the contract; publishes the GitHub
  release with these notes as its body and `versions.yaml`,
  `matrix/results.json` and `checksums.txt` as assets. It pushes no image.
- **`scripts/release-notes.sh`**: prints the notes of a version (the
  section up to its `---`); CI runs it for the version `versions.yaml`
  names, so a version bump without notes fails.
- **RELEASE.md**: how a release is made, and the notes of every version.
- `versions.yaml` names this version: v0.1.2 was tagged while it still
  said 0.1.1.

The images, the adapters, the contract (1.0), every upstream pin and the
matrix are unchanged from v0.1.2.

---

## v0.1.2

**Date:** 2026-10-27
**Previous release:** v0.1.1

## Summary

The interoperability matrix, regenerated from go-profinet's interop suite
on main (4db9288), covers DCP Hello, PDev port checks, shared device with
two IO controllers on p-net, and tshark/scapy decoding of the MRP, PTCP
and system-redundancy codecs ([#3](https://github.com/otfabric/profinet-interop/pull/3)).

| Peer | pass | fail | n/a | peer-deviation |
|------|-----:|-----:|----:|---------------:|
| p-net | 55 (was 45) | 0 | 0 | 0 |
| pnio-rs | 12 | 0 | 2 | 0 |
| profinet-py | 22 | 0 | 0 | 2 |
| pnio-dcp | 8 | 0 | 0 | 0 |
| scapy | 7 (was 4) | 0 | 0 | 0 |
| tshark | 7 (was 4) | 0 | 0 | 0 |
| tshark and scapy | 2 | 0 | 0 | 0 |

No change to the images, the adapters or any upstream pin
(`versions.yaml`); images are still built locally only (GPL). This tag's
`versions.yaml` still says 0.1.1 (fixed in v0.1.3).

---

## v0.1.1

**Date:** 2026-10-26
**Previous release:** v0.1.0

## Summary

tshark adapter: heuristic dissectors run first (`udp.try_heuristic_first`),
so PNIO RPC on an ephemeral UDP port that another protocol registered
(37008, TZSP) decodes as DCE/RPC instead of a malformed TZSP frame. This
made go-profinet's interop suite fail now and then
([#2](https://github.com/otfabric/profinet-interop/pull/2)).

Soaked with go-profinet: 25 parallel interop runs, all green. Images are
still built locally only (GPL); every upstream pin is unchanged from v0.1.0
(`versions.yaml`).

---

## v0.1.0

**Date:** 2026-10-26

## Summary

First release of the PROFINET reference-implementation containers for OT
Fabric interoperability testing.

## Adapters (contract 1.0)

| Adapter | Upstream | Pin | Roles |
|---------|----------|-----|-------|
| pnet | rt-labs p-net | ea5e554 | IO-Device |
| pnio-rs | pnio-rs | v0.1.0 | IO-Device |
| profinet-py | profinet-py | 0.6.6 | IO-Controller, DCP tool |
| pnio-dcp | pnio-dcp | 1.2.0 | DCP requester |
| scapy | Scapy | pinned in versions.yaml | frame crafting |
| tshark | Wireshark tshark | pinned in versions.yaml | decoder |

Matrix against go-profinet v0.1.0: 95 pass, 0 fail, 2 n/a, 2 documented
peer deviations (docs/MATRIX.md).

## No published images

p-net, profinet-py, Scapy and tshark are GPL: images are built locally with
`make images` and never pushed. Every upstream and base image is pinned in
`versions.yaml`. The containers are for test networks only (p-net's tree
predates its v1.0.2 security fixes). See THIRD_PARTY_NOTICES.md.

---
