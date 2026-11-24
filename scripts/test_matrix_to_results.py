#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Tests of scripts/matrix-to-results.py."""

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

import interop_result

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("matrix_to_results", os.path.join(HERE, "matrix-to-results.py"))
mr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mr)

IDS = {("TestA", "one"): "a.one", ("TestA", "two"): "a.two"}
WAIVERS = [{"id": "w", "scope": "device@p-net", "evidence": "https://example.com/x", "scenarios": re.compile(r"a\.two")}]
SUT = {"name": "go-profinet", "version": "v1.2.3", "revision": "0123456789abcdef0123456789abcdef01234567"}


def row(outcome, feature="one", detail="", peer="p-net"):
    return {"test": "TestA", "feature": feature, "peer": peer, "peerRole": "device", "goRole": "IO-Controller",
            "image": "x:dev", "outcome": outcome, "detail": detail}


def convert(*rows, waivers=WAIVERS, sut=SUT):
    doc = mr.convert(list(rows), "2026-10-29T00:15:30+00:00", "make matrix", IDS, waivers, {}, sut)
    doc["summary"] = interop_result.summarize(doc["results"])
    return doc


class Convert(unittest.TestCase):
    def test_a_pass_passes(self):
        doc = convert(row("pass"))
        self.assertEqual(interop_result.schema_errors(doc), [])
        self.assertEqual(interop_result.problems(doc), [])
        self.assertEqual(doc["results"][0]["roles"], {"sut": "go-profinet", "peer": "pnet", "sut-role": "IO-Controller"})

    def test_na_is_unsupported_and_no_pass_fails(self):
        doc = convert(row("n/a", detail="not implemented"))
        self.assertEqual(doc["results"][0]["outcome"], "unsupported")
        self.assertEqual(doc["results"][0]["reason"], "not implemented")
        self.assertTrue(interop_result.problems(doc))

    def test_peer_deviation_is_known_difference(self):
        doc = convert(row("pass"), row("peer-deviation", "two", "it deviates"))
        self.assertEqual(interop_result.schema_errors(doc), [])
        self.assertEqual((doc["results"][1]["outcome"], doc["results"][1]["waiver"]), ("known-difference", "w"))
        self.assertEqual(interop_result.problems(doc), [])

    def test_peer_deviation_without_a_waiver_fails(self):
        doc = convert(row("pass"), row("peer-deviation", "two", "it deviates"), waivers=[])
        self.assertEqual(doc["results"][1]["outcome"], "fail")
        self.assertTrue(interop_result.problems(doc))

    def test_stale_waiver_fails(self):
        doc = convert(row("pass"), row("pass", "two"))
        self.assertFalse(doc["waivers"][0]["reproduced"])
        self.assertTrue(interop_result.problems(doc))

    def test_a_waiver_that_did_not_run_is_not_listed(self):
        self.assertEqual(convert(row("pass"))["waivers"], [])

    def test_unknown_check_stops(self):
        with self.assertRaises(SystemExit):
            convert(row("pass", "three"))

    def test_two_peers_in_one_row(self):
        doc = convert(row("pass", peer="tshark/scapy"))
        self.assertEqual(doc["results"][0]["roles"]["peer-2"], "scapy")

    def test_the_profile_records_variant_is_not_independent(self):
        doc = convert(row("pass", peer="p-net, profile-records variant"))
        self.assertEqual(doc["results"][0]["roles"]["peer"], "pnet-profile")
        impl = {i["name"]: i for i in doc["implementations"]}
        self.assertFalse(impl["pnet-profile"]["independent"])
        self.assertTrue(convert(row("pass"))["implementations"][1]["independent"])

    def test_the_document_names_the_sut_version_given(self):
        doc = convert(row("pass"))
        self.assertEqual(doc["implementations"][0], {"name": "go-profinet", "version": "v1.2.3",
                                                      "revision": SUT["revision"], "independent": False})
        self.assertEqual(interop_result.schema_errors(doc), [])
        without_revision = convert(row("pass"), sut={"name": "go-profinet", "version": "v1.2.3"})
        self.assertEqual(without_revision["implementations"][0], {"name": "go-profinet", "version": "v1.2.3", "independent": False})

    def test_a_matrix_without_the_sut_version_stops(self):
        for sut in (None, {}, {"name": "go-profinet"}, {"name": "go-profinet", "version": ""}, {"version": "  "}):
            with self.subTest(sut=sut), self.assertRaises(SystemExit):
                convert(row("pass"), sut=sut)


class Matrix(unittest.TestCase):
    """scripts/matrix.py records the go-profinet that ran as "sut"."""

    def run_matrix(self, *args):
        with tempfile.TemporaryDirectory() as tmp:
            results = os.path.join(tmp, "results")
            os.mkdir(results)
            with open(os.path.join(results, "TestA.json"), "w") as f:
                json.dump({"test": "TestA", "peer": "p-net", "role": "device", "image": "x:dev",
                           "checks": [{"feature": "one", "outcome": "pass"}]}, f)
            out_json, out_md = os.path.join(tmp, "results.json"), os.path.join(tmp, "MATRIX.md")
            p = subprocess.run([sys.executable, os.path.join(HERE, "matrix.py"), results, out_json, out_md, *args],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            doc = None
            if os.path.exists(out_json):
                with open(out_json) as f:
                    doc = json.load(f)
            return p.returncode, p.stderr, doc

    def test_the_sut_version_and_revision_are_recorded(self):
        code, err, doc = self.run_matrix("go-profinet v1.2.3 against profinet-interop v0.1.0", "v1.2.3", SUT["revision"])
        self.assertEqual(code, 0, err)
        self.assertEqual(doc["sut"], SUT)
        code, err, doc = self.run_matrix("", "v1.2.3")
        self.assertEqual(code, 0, err)
        self.assertEqual(doc["sut"], {"name": "go-profinet", "version": "v1.2.3"})

    def test_no_sut_version_is_refused(self):
        for args in ((), ("source",), ("source", ""), ("source", " ")):
            with self.subTest(args=args):
                code, err, doc = self.run_matrix(*args)
                self.assertNotEqual(code, 0)
                self.assertIn("SUT_VERSION", err)
                self.assertIsNone(doc)


class Committed(unittest.TestCase):
    def test_the_committed_matrix_converts_and_passes(self):
        with open(os.path.join(HERE, "..", "matrix", "results.json")) as f:
            matrix = json.load(f)
        doc = mr.convert(matrix["rows"], matrix["generated"], "make matrix", mr.load_ids(), mr.load_waivers(), mr.pins(),
                         matrix.get("sut"))
        doc["summary"] = interop_result.summarize(doc["results"])
        self.assertEqual(interop_result.problems(doc), [])
        self.assertEqual(len({r["id"] for r in doc["results"]}), len(doc["results"]))

    def test_the_committed_document_names_the_sut_of_the_matrix(self):
        with open(os.path.join(HERE, "..", "matrix", "results.json")) as f:
            sut = json.load(f)["sut"]
        with open(os.path.join(HERE, "..", "matrix", "interop-result-v1.json")) as f:
            committed = json.load(f)
        self.assertEqual(committed["implementations"][0], mr.system_under_test(sut))

    def test_every_waiver_is_used(self):
        with open(os.path.join(HERE, "..", "matrix", "results.json")) as f:
            matrix = json.load(f)
        doc = mr.convert(matrix["rows"], matrix["generated"], "make matrix", mr.load_ids(), mr.load_waivers(), mr.pins(),
                         matrix.get("sut"))
        self.assertEqual({w["id"] for w in doc["waivers"]}, {w["id"] for w in mr.load_waivers()})


if __name__ == "__main__":
    unittest.main()
