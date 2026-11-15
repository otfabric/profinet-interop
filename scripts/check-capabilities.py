#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Checks a capability document against schemas/capabilities.schema.json.

    <image> print-capabilities | scripts/check-capabilities.py ADAPTER
    scripts/check-capabilities.py ADAPTER FILE

The document must be valid against the schema (docs/CONTAINER_CONTRACT.md,
print-capabilities) and name ADAPTER as its adapter. Prints one "FAIL" line
per problem. The exit status is 1 when the document is not valid, 2 on a
usage error or when the jsonschema package is not installed
(pip install jsonschema).
"""

import json
import os
import sys

SCHEMA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schemas", "capabilities.schema.json")


def problems(doc, adapter):
    """Why doc is not a capability document of adapter; empty when it is."""
    import jsonschema

    with open(SCHEMA) as f:
        validator = jsonschema.Draft202012Validator(json.load(f))
    errors = sorted(validator.iter_errors(doc), key=lambda e: [str(p) for p in e.absolute_path])
    out = ["%s: %s" % ("/".join(str(p) for p in e.absolute_path) or "(document)", e.message) for e in errors]
    if isinstance(doc, dict) and doc.get("adapter") != adapter:
        out.append("adapter: %r, not %r" % (doc.get("adapter"), adapter))
    return out


def main(argv):
    if len(argv) not in (1, 2) or argv[0].startswith("-"):
        print(__doc__, file=sys.stderr)
        return 2
    try:
        import jsonschema  # noqa: F401
    except ImportError:
        print("check-capabilities: the jsonschema package is required (pip install jsonschema)", file=sys.stderr)
        return 2
    if len(argv) == 2:
        with open(argv[1]) as f:
            text = f.read()
    else:
        text = sys.stdin.read()
    try:
        doc = json.loads(text)
    except ValueError as e:
        print("FAIL not a JSON document: %s" % e)
        return 1
    bad = problems(doc, argv[0])
    for p in bad:
        print("FAIL " + p)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
