# AGENTS.md — profinet-interop

## What this is

Independent PROFINET IO implementations (p-net, pnio-rs, profinet-py, pnio-dcp, umrp, mrp, Net-SNMP) and independent decoders (scapy, tshark) in containers behind one command-line contract, used as oracles by go-profinet on a real Layer 2 network. Profile: **interoperability**.

## Organisation standards

This repository follows **otfabric/engineering policy 1.2**, profile **interoperability** (`.otfabric/policy.yaml`, mode `enforce`). Where this file and the organisation standards disagree, this file wins here — say so in your report.

## Where the truth lives

| Question | Source |
|---|---|
| Container commands, documents, exit codes | docs/CONTAINER_CONTRACT.md (`contract_version` in versions.yaml) |
| Pins (upstream revision, base image digests, published?) | versions.yaml, checked by `make check-versions` |
| Results and discrepancies | docs/MATRIX.md, matrix/results.json, docs/INTEROPERABILITY.md |

## Hard rules

1. Nothing floats: upstreams by commit, version or hash, base images by digest. `make check-versions` must pass.
2. No image is pushed: GPL stacks are built by each user. CI fails on a target that pushes.
3. Results come from go-profinet's interop runs; `n/a` and `peer-deviation` are never counted as passes.
4. Contract changes bump `contract_version` and reach every adapter and docs/CONTAINER_CONTRACT.md in the same change.
5. Licences: every component in THIRD_PARTY_NOTICES.md, licence files under `/licenses/` in each image.
6. The release tag equals `interop_version`.

## Commands

| When you change… | Run |
|---|---|
| anything | `make check-versions lint` |
| an adapter | `make image-<adapter> contract` |
| all images | `make images smoke` |
| results | `make matrix RESULTS=<dir>` |
| a release | `make release-notes` |

## Git and releases

Branches and PRs. Do not push to `main`, push tags or publish images unless the maintainer asks in the session.
