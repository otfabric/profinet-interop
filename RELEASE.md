# profinet-interop Releases

## How a release is made

1. Write the notes of the version below and set `interop_version` in
   `versions.yaml` to it, in the same change. CI fails when RELEASE.md has
   no notes for the version `versions.yaml` names.
2. CI is green on the commit to release; when the matrix changed, it is
   regenerated from go-profinet's Interop workflow (`make matrix
   RESULTS=dir`).
3. Tag `vX.Y.Z` and push the tag. The release workflow
   (`.github/workflows/release.yml`) checks that the tag, `versions.yaml`
   and the notes agree, builds every image on amd64 and arm64 and checks it
   against the contract, then publishes the GitHub release with
   `versions.yaml`, the matrix results and their checksums. **No image is
   published**: p-net, profinet-py, umrp, mrp, Scapy and tshark are GPL, and every
   user builds the images from upstream (`make images`).
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

## v0.3.0

**Date:** 2026-10-28
**Previous release:** v0.2.1

## Summary

Two independent MRP implementations as ring nodes, so that go-profinet's
MRP manager and client are tested against software that is not
go-profinet: **umrp** (giometti/umrp, user space, runs on any Linux
kernel) and **mrp** (microchip-ung/mrp, unmodified, on the kernel's
bridge MRP support where the host kernel has it). Contract 1.1.

## Changes

- New adapter `umrp`: umrp v4.0 with `ifdriver_bridge.c` (GPL-2.0, this
  repository's only GPL file), which applies umrp's ring port states to a
  Linux bridge through an nftables set of blocked ports, so no kernel MRP
  support is needed. Commands `node` and `status` (ring state, port states,
  FDB flushes, probe frames received).
- New adapter `mrp`: microchip-ung/mrp `177717e` (after v1.2) with libcfm,
  unmodified; needs a host kernel with `CONFIG_BRIDGE_MRP` (GitHub-hosted
  runners: yes; Docker Desktop: no). `kernel-mrp` tells; `node` prints
  `unsupported` and exits 3 without it.
- Contract 1.1 (additions only): the MRP ring node role (`node`, `status`,
  `kernel-mrp`, exit code 3), and scapy's `decode` reports the frames it
  has no dissector for (MRP, PTCP) as `notDissected`: they were counted as
  decoded before, which overstated scapy's evidence for MRP.
- `scripts/latest-upstream.py`, the candidate workflow and
  `scripts/check-versions.sh` cover both new adapters (umrp by tag, mrp by
  the head of its default branch).
- The matrix is regenerated from go-profinet's interop suite with the MRP
  ring tests.

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
