# Requirements

What this repository must do and must not do. [docs/CONTAINER_CONTRACT.md](docs/CONTAINER_CONTRACT.md)
is the specification that follows from it.

## Purpose

Independent PROFINET IO implementations and decoders, in containers that all
behave the same way, so that an implementation under test can be run against
real implementation diversity on Layer 2 without owning any of it.

## R1 - Repository isolation

- R1.1 The adapters and the self-test (`adapters/`, `scripts/lib.sh`,
  `smoke.sh`, `interop.sh`, `interop.py`, `check-contract.sh`,
  `tests/cases.tsv`) do not import, build, link against or depend on any
  library under test, and contain no expectation specific to one; CI checks
  that they do not name one. The one exception is `own/` with its workflow:
  images of OT Fabric's own stacks, published for others to test against
  (`own/go-profinet/README.md`). The rest of the repository does not know
  them, and they are not part of a release. The matrix scripts
  (`matrix.py`, `matrix-to-results.py`) turn go-profinet's interop results
  into the matrix and name it for that reason.
- R1.2 A consumer depends on the documented contract and images built from a
  release of this repository only.
- R1.3 No third-party code from here is copied into a consumer, and the
  contract does not shape a consumer's public API.
