# profinet-interop-otfabric

[go-profinet](https://github.com/otfabric/go-profinet), OT Fabric's own
PROFINET IO stack, behind the [container contract](../../docs/CONTAINER_CONTRACT.md)
(adapter `otfabric`), so that other stacks can test against it: an IO-Device,
an IO-Controller and a DCP tool on a real Layer 2 network. It is the only
image this repository publishes. Unlike the references, it is not
independent: its tags are go-profinet versions, and no harness release
contains it.

**For testing only.** The IO-Device accepts any IO-Controller, DCP Set and
Reset from anyone on the network, as PROFINET devices do. Run it only on an
isolated test network (a Docker bridge network). Old images stay available,
so check [go-profinet advisories](https://github.com/otfabric/go-profinet/security/advisories)
for the version you pull.

**Not an independent implementation.** The image declares
`upstream.independentEngine: false`, and `results.json` records
`independent: false`. A result against it says nothing independent about
go-profinet when OT Fabric produces it. A result you publish, naming the
implementation and version, is independent evidence, and we would like to hear
about it.

## Use

```sh
docker network create --subnet 10.77.0.0/24 pn
docker run -d --name otf --network pn --ip 10.77.0.30 --cap-add NET_RAW --cap-add NET_ADMIN \
  ghcr.io/otfabric/profinet-interop-otfabric:<tag> device --station otf-dut --gsdml-out /run/profinet-interop/otf-dut.xml
docker exec otf cat /run/profinet-interop/otf-dut.xml > otf-dut.xml    # its GSDML, for your controller
docker run --rm --network pn --ip 10.77.0.4 --cap-add NET_RAW --cap-add NET_ADMIN \
  ghcr.io/otfabric/profinet-interop-otfabric:<tag> dcp identify
```

As an IO-Controller of your device: `controller --station NAME --model
FILE.xml [--advanced] [--im0] [--duration 3s]` with your GSDML mounted.
The commands, flags and documents are in the contract's section `otfabric`.

`<tag>` is a go-profinet version such as `v0.7.0`, or `latest`, the newest
one published. A rebuild of a version replaces its tag, so pin the digest if
you need an exact build. The digest is in the summary of the
[workflow run](https://github.com/otfabric/profinet-interop/actions/workflows/own-go-profinet.yml),
and `docker run --rm <image> version` prints the version.

| | |
|---|---|
| Upstream | go-profinet, the latest release when the image was built |
| Licence | MIT; every module's licence is in the image under `/licenses` |
| Adapter name | `otfabric` |
| Language | Go |
| Protocol engine | OT Fabric's own |
| Roles | `device`, `controller`, `dcp-tool` |

The sources are go-profinet's interop node (`interop/otfnode` of the
go-profinet release, copied unchanged) and `contract.go`, the contract's
commands (`version`, `print-capabilities`, exit 2 for an unknown command,
`--iface`).

## Why it is apart from the other adapters

`REQUIREMENTS.md` R1: nothing under `adapters/`, the self-test scripts or
`tests/` knows a library under test, and CI enforces that. This directory
and `.github/workflows/own-go-profinet.yml` are the one exception. The
scripts take the image through `ADAPTER_IMAGE_otfabric`.

No release loop can form (`otfabric/engineering` ADR-0012). This image is built
by hand, from the latest go-profinet release, and nothing is committed: this
repository has no pin of go-profinet to bump. No release or required check
of go-profinet needs the image, and go-profinet commits no pin of it. It is
not in a harness release.

## Publishing

Run the **Own stack (go-profinet)** workflow by hand, from `main`. It finds
the latest go-profinet release and the latest harness release, and prints
them. No reference image is published, so it builds the references the
self-test needs (pnio-dcp, profinet-py, pnio-rs) from that harness release.
It builds the image, runs the smoke test and the cross-stack self-test
(`GATE=otfabric`: only the pairs that involve the image, the image against
itself too) on both architectures, then publishes `:<go-profinet version>` and `:latest`. Run
from a branch, it stops before publishing. Nothing runs it automatically, so
after a go-profinet release the image stays on the old version until
someone does.

```sh
make images                                                   # the references
make -f own/go-profinet/Makefile image smoke interop          # from the repository root
```

## What it cannot do

- MRP: go-profinet's ring node is not behind the contract's `node` and
  `status` commands here; the role `mrp-node` is not declared.
- SNMP is served by the device (`--snmp COMMUNITY`), but the image has no
  SNMP manager role.
