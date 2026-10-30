#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Tests of scripts/matrix-to-results.py."""

import importlib.util
import json
import os
import re
import unittest

import interop_result

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("matrix_to_results", os.path.join(HERE, "matrix-to-results.py"))
mr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mr)

IDS = {("TestA", "one"): "a.one", ("TestA", "two"): "a.two"}
WAIVERS = [{"id": "w", "scope": "device@p-net", "evidence": "https://example.com/x", "scenarios": re.compile(r"a\.two")}]


def row(outcome, feature="one", detail="", peer="p-net"):
    return {"test": "TestA", "feature": feature, "peer": peer, "peerRole": "device", "goRole": "IO-Controller",
            "image": "x:dev", "outcome": outcome, "detail": detail}


def convert(*rows, waivers=WAIVERS):
    doc = mr.convert(list(rows), "2026-10-29T00:15:30+00:00", "make matrix", IDS, waivers, {})
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


class Committed(unittest.TestCase):
    def test_the_committed_matrix_converts_and_passes(self):
        with open(os.path.join(HERE, "..", "matrix", "results.json")) as f:
            matrix = json.load(f)
        doc = mr.convert(matrix["rows"], matrix["generated"], "make matrix", mr.load_ids(), mr.load_waivers(), mr.pins())
        doc["summary"] = interop_result.summarize(doc["results"])
        self.assertEqual(interop_result.problems(doc), [])
        self.assertEqual(len({r["id"] for r in doc["results"]}), len(doc["results"]))

    def test_every_waiver_is_used(self):
        with open(os.path.join(HERE, "..", "matrix", "results.json")) as f:
            matrix = json.load(f)
        doc = mr.convert(matrix["rows"], matrix["generated"], "make matrix", mr.load_ids(), mr.load_waivers(), mr.pins())
        self.assertEqual({w["id"] for w in doc["waivers"]}, {w["id"] for w in mr.load_waivers()})


if __name__ == "__main__":
    unittest.main()
