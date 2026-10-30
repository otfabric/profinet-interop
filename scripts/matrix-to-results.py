#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Turn the interoperability matrix into the organisation's interop-result-v1.

    scripts/matrix-to-results.py <matrix/results.json> <interop-result-v1.json>

matrix/results.json stays what scripts/matrix.py writes: the rows of
go-profinet's interop results, which carry no host, duration or time of their
own. The host is therefore "unrecorded", durationMs 0, and startedAt and
finishedAt are the time the matrix was generated. Outcomes: n/a (the peer does not implement the feature)
becomes unsupported; peer-deviation becomes known-difference with its waiver
from tests/known-differences.tsv, or fail when it has none. IDs come from
matrix/ids.tsv. The exit status is 1 when the run failed: a fail, a waiver that
no longer reproduces, or no pass at all (scripts/interop_result.py).
"""

import json
import re
import sys
from pathlib import Path

import interop_result

ROOT = Path(__file__).resolve().parent.parent
OUTCOME = {"pass": "pass", "fail": "fail", "n/a": "unsupported", "peer-deviation": "known-difference"}
# The peer of a matrix row -> the implementations of versions.yaml it names.
PEERS = {"p-net": ["pnet"], "Net-SNMP": ["netsnmp"], "tshark/scapy": ["tshark", "scapy"]}
SUT = "go-profinet"


def table(path):
    for line in Path(path).read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            yield line.split("\t")


def load_ids(path=ROOT / "matrix" / "ids.tsv"):
    return {(test, feature): rid for test, feature, rid in table(path)}


def load_waivers(path=ROOT / "tests" / "known-differences.tsv"):
    return [{"id": i, "scope": scope, "evidence": url, "scenarios": re.compile(regex)}
            for i, scope, _, url, _, regex in table(path)]


def pins(path=ROOT / "versions.yaml"):
    """implementation -> version, revision and licence, from versions.yaml."""
    out, name, inside = {}, None, False
    for line in Path(path).read_text().splitlines():
        if re.match(r"^\S", line):
            inside = line.startswith("implementations:")
        m = re.match(r"^  ([A-Za-z0-9._-]+):\s*$", line)
        if inside and m:
            name = m.group(1)
            out[name] = {}
        m = re.match(r'^    (version|revision|license): "?([^"#]+?)"?\s*(#.*)?$', line)
        if inside and name and m:
            out[name][m.group(1)] = m.group(2)
    return out


def implementation(name, versions):
    pin = versions.get(name, {})
    i = {"name": name, "version": pin.get("version") or pin.get("revision", "unrecorded")[:12], "independent": True}
    for key in ("revision", "license"):
        if key in pin:
            i[key] = pin[key]
    return i


def convert(rows, generated, reproduce, ids, waivers, versions):
    results, peers, deviating, ran = [], {}, set(), set()
    for row in rows:
        key = (row["test"], row["feature"])
        if key not in ids:
            raise SystemExit("no stable ID in matrix/ids.tsv for %s: %s" % key)
        rid, outcome = ids[key], OUTCOME[row["outcome"]]
        names = PEERS.get(row["peer"], [row["peer"]])
        peers.update(dict.fromkeys(names))
        roles = {"sut": SUT}
        roles.update({"peer" if len(names) == 1 else "peer-%d" % (n + 1): name for n, name in enumerate(names)})
        res = {"id": rid, "suite": rid.split(".")[0], "feature": row["feature"], "roles": roles, "outcome": outcome, "durationMs": 0}
        if row["goRole"] != "-":
            res["roles"]["sut-role"] = row["goRole"]
        if outcome != "pass":
            res["reason"] = row["detail"] or row["outcome"]
        waiver = next((w for w in waivers if w["scenarios"].fullmatch(rid)), None)
        if waiver:
            ran.add(waiver["id"])
        if outcome == "known-difference":
            if waiver:
                res["waiver"] = waiver["id"]
                deviating.add(waiver["id"])
            else:
                res["outcome"] = "fail"
                res["reason"] = "peer-deviation without a line in tests/known-differences.tsv: " + res["reason"]
        results.append(res)
    implementations = [{"name": SUT, "version": "unrecorded", "independent": False}]
    implementations += [implementation(name, versions) for name in sorted(peers)]
    return {"schemaVersion": "1.0", "repository": "otfabric/profinet-interop",
            "interopVersion": interop_result.version_field(str(ROOT), "interop_version"),
            "contractVersion": interop_result.version_field(str(ROOT), "contract_version"),
            "gitSha": interop_result.git_sha(str(ROOT)), "startedAt": generated, "finishedAt": generated,
            "host": {"os": "unrecorded", "arch": "unrecorded"}, "implementations": implementations,
            "waivers": [{"id": w["id"], "scope": w["scope"], "evidence": w["evidence"], "reproduced": w["id"] in deviating}
                        for w in waivers if w["id"] in ran],
            "reproduce": reproduce, "results": results}


def main(argv):
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    matrix = json.loads(Path(argv[0]).read_text())
    reproduce = "PROFINET_INTEROP_RESULTS=dir make -C ../go-profinet interop && make matrix RESULTS=dir"
    doc = convert(matrix["rows"], matrix["generated"], reproduce, load_ids(), load_waivers(), pins())
    interop_result.write(argv[1], doc)
    bad = interop_result.schema_errors(doc) + interop_result.problems(doc)
    print("%s: %s" % (argv[1], ", ".join("%d %s" % (doc["summary"][o], o) for o in interop_result.OUTCOMES)))
    for p in bad:
        print("FAIL " + p, file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
