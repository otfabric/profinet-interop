#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Tests of scripts/check-capabilities.py and schemas/capabilities.schema.json."""

import copy
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ADAPTERS = os.path.join(HERE, "..", "adapters")
spec = importlib.util.spec_from_file_location("check_capabilities", os.path.join(HERE, "check-capabilities.py"))
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)

try:
    import jsonschema  # noqa: F401
    HAVE_JSONSCHEMA = True
except ImportError:
    HAVE_JSONSCHEMA = False

DOC = {"schemaVersion": "1.0", "adapter": "example", "implementation": "example", "version": "1.0", "license": "MIT",
       "roles": ["device", "dcp-tool"],
       "features": {"dcpIdentify": True, "dcpSetIP": "same-suite-only", "dcpIdentifyFilters": ["all", "name"], "lldp": False},
       "upstream": {"name": "example", "version": "1.0", "revision": "0123456", "independentEngine": True}}


def heredoc(adapter):
    """The capability document an entrypoint.sh prints from its JSON here-document."""
    with open(os.path.join(ADAPTERS, adapter, "entrypoint.sh")) as f:
        text = f.read().replace("\r\n", "\n")
    m = re.search(r"cat <<'JSON'\n(.*?)\nJSON\n", text, re.S)
    if not m:
        raise AssertionError("%s/entrypoint.sh has no JSON here-document" % adapter)
    return json.loads(m.group(1))


@unittest.skipUnless(HAVE_JSONSCHEMA, "the jsonschema package is not installed")
class Schema(unittest.TestCase):
    def assertValid(self, doc, adapter):
        self.assertEqual(cc.problems(doc, adapter), [])

    def assertInvalid(self, doc, adapter="example"):
        self.assertTrue(cc.problems(doc, adapter), json.dumps(doc))

    def changed(self, path, value):
        doc = copy.deepcopy(DOC)
        *parents, key = path
        target = doc
        for p in parents:
            target = target[p]
        if value is KeyError:
            del target[key]
        else:
            target[key] = value
        return doc

    def test_the_documents_of_the_shell_adapters_are_valid(self):
        for adapter in ("pnet", "pnio-rs", "mrp", "umrp"):
            with self.subTest(adapter=adapter):
                self.assertValid(heredoc(adapter), adapter)

    def test_the_document_of_netsnmp_is_valid(self):
        p = subprocess.run([sys.executable, os.path.join(ADAPTERS, "netsnmp", "adapter.py"), "print-capabilities"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertValid(json.loads(p.stdout), "netsnmp")

    def test_a_document_without_features_is_valid(self):
        self.assertValid(self.changed(["features"], KeyError), "example")

    def test_a_feature_that_is_not_a_boolean_is_refused(self):
        for value in ("true", 1, None, ["true"]):
            with self.subTest(value=value):
                self.assertInvalid(self.changed(["features", "lldp"], value))

    def test_a_qualified_feature_is_a_boolean_or_a_qualification(self):
        self.assertValid(self.changed(["features", "dcpSetIP"], True), "example")
        for value in ("true", "false", "", 0):
            with self.subTest(value=value):
                self.assertInvalid(self.changed(["features", "dcpSetIP"], value))

    def test_an_unknown_feature_is_refused(self):
        self.assertInvalid(self.changed(["features", "lldpp"], True))

    def test_an_unknown_or_missing_role_is_refused(self):
        for roles in (["io-device"], [], "device", ["device", "device"]):
            with self.subTest(roles=roles):
                self.assertInvalid(self.changed(["roles"], roles))

    def test_upstream_needs_a_boolean_independent_engine(self):
        for value in (KeyError, "false", 0, None):
            with self.subTest(value=value):
                self.assertInvalid(self.changed(["upstream", "independentEngine"], value))
        self.assertInvalid(self.changed(["upstream"], KeyError))

    def test_another_schema_version_or_an_unknown_field_is_refused(self):
        self.assertInvalid(self.changed(["schemaVersion"], "2.0"))
        self.assertInvalid(self.changed(["feautres"], {}))

    def test_another_adapter_is_refused(self):
        self.assertEqual(cc.problems(DOC, "other"), ["adapter: 'example', not 'other'"])


@unittest.skipUnless(HAVE_JSONSCHEMA, "the jsonschema package is not installed")
class Command(unittest.TestCase):
    def run_check(self, adapter, doc):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "caps.json")
            with open(path, "w") as f:
                f.write(doc if isinstance(doc, str) else json.dumps(doc))
            with open(path) as f:
                p = subprocess.run([sys.executable, os.path.join(HERE, "check-capabilities.py"), adapter],
                                   stdin=f, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        return p.returncode, p.stdout

    def test_exit_status(self):
        self.assertEqual(self.run_check("example", DOC), (0, ""))
        code, out = self.run_check("example", dict(DOC, roles=["io-device"]))
        self.assertEqual(code, 1)
        self.assertIn("FAIL roles/0: ", out)
        self.assertEqual(self.run_check("example", "{")[0], 1)
        self.assertEqual(self.run_check("--help", DOC)[0], 2)


FAKE_DOCKER = """#!/bin/sh
# docker run --rm IMAGE COMMAND, as scripts/check-contract.sh calls it.
case "$4" in
version) echo "example 1.0" ;;
print-capabilities) cat "$FAKE_CAPABILITIES" ;;
*) exit 2 ;;
esac
"""


@unittest.skipUnless(HAVE_JSONSCHEMA, "the jsonschema package is not installed")
class ContractScript(unittest.TestCase):
    """scripts/check-contract.sh against an image whose docker run is faked."""

    def run_contract(self, doc):
        with tempfile.TemporaryDirectory() as tmp:
            docker = os.path.join(tmp, "docker")
            with open(docker, "w") as f:
                f.write(FAKE_DOCKER)
            os.chmod(docker, 0o755)
            # The python3 of check-contract.sh is this one, which has jsonschema.
            os.symlink(sys.executable, os.path.join(tmp, "python3"))
            caps = os.path.join(tmp, "caps.json")
            with open(caps, "w") as f:
                json.dump(doc, f)
            env = dict(os.environ, PATH=tmp + os.pathsep + os.environ.get("PATH", ""), FAKE_CAPABILITIES=caps)
            p = subprocess.run(["bash", os.path.join(HERE, "check-contract.sh"), "dev", "example"], env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        return p.returncode, p.stdout

    def test_a_valid_document_passes(self):
        code, out = self.run_contract(DOC)
        self.assertEqual(code, 0, out)

    def test_a_feature_that_is_not_a_boolean_fails(self):
        doc = copy.deepcopy(DOC)
        doc["features"]["lldp"] = "true"
        code, out = self.run_contract(doc)
        self.assertEqual(code, 1, out)
        self.assertIn("bad capability document", out)

    def test_an_unknown_role_fails(self):
        code, out = self.run_contract(dict(DOC, roles=["io-device"]))
        self.assertEqual(code, 1, out)
        self.assertIn("bad capability document", out)


if __name__ == "__main__":
    unittest.main()
