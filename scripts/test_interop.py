# SPDX-License-Identifier: MIT
"""Unit tests of scripts/interop.py that need no Docker."""

import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("interop", os.path.join(HERE, "interop.py"))
interop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(interop)


class TestInterop(unittest.TestCase):
    def test_cases(self):
        cases = interop.load_cases()
        ids = [c["id"] for c in cases]
        self.assertEqual(len(ids), len(set(ids)))
        for c in cases:
            self.assertRegex(c["id"], r"^[a-z0-9][a-z0-9._-]*$")
            self.assertIn(c["client"], ("dcp-tool", "controller"))
            self.assertEqual(c["server"], "device")
        self.assertIn("dcp.identify", ids)
        self.assertIn("ar.connect", ids)

    def test_image_of(self):
        old = dict(os.environ)
        try:
            os.environ.pop("ADAPTER_IMAGE_pnio_rs", None)
            os.environ["TAG"] = "x"
            self.assertEqual(interop.image_of("pnio-rs"), "profinet-interop-pnio-rs:x")
            os.environ["ADAPTER_IMAGE_pnio_rs"] = "example/img:1"
            self.assertEqual(interop.image_of("pnio-rs"), "example/img:1")
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_json_lines(self):
        out = 'noise\n{"event":"start","mac":"aa"}\n{broken\n {"event":"stop"}\n'
        self.assertEqual(interop.json_lines(out), [{"event": "start", "mac": "aa"}, {"event": "stop"}])
        self.assertEqual(interop.norm_mac("AA-BB-CC-00-11-22"), "aa:bb:cc:00:11:22")


if __name__ == "__main__":
    unittest.main()
