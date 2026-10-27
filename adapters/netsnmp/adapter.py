"""profinet-interop adapter for Net-SNMP's command-line manager.

  profinet-interop snmp OP --host IP [--port N] [--community C] [--version 1|2c]
        [--timeout S] [--retries N] [--max-rep N] [--non-rep N] OID... | --set OID TYPE VALUE
  profinet-interop print-capabilities | version

OP is get, getnext, bulkget, walk, bulkwalk or set. It runs the Net-SNMP
tool with numeric OIDs, raw TimeTicks and octet strings in hex, and prints
one JSON document: the variable bindings Net-SNMP decoded (oid, type as
Net-SNMP names it, value; octet strings also as hex, TimeTicks as their
number of hundredths), the exceptions it
reported (noSuchObject, noSuchInstance, endOfMibView), the error status of
an error response (noSuchName, notWritable, tooBig, ...), a timeout, and the
tool's exit status.
"""

import json
import re
import subprocess
import sys

TOOLS = {"get": "snmpget", "getnext": "snmpgetnext", "bulkget": "snmpbulkget", "walk": "snmpwalk",
         "bulkwalk": "snmpbulkwalk", "set": "snmpset"}
EXCEPTIONS = {
    "No Such Object available on this agent at this OID": "noSuchObject",
    "No Such Instance currently exists at this OID": "noSuchInstance",
    "No more variables left in this MIB View (It is past the end of the MIB tree)": "endOfMibView",
}
LINE = re.compile(r"^(\.?[0-9.]+) = (.*)$")


def version():
    try:
        with open("/licenses/net-snmp/VERSION") as f:
            return f.read().strip()
    except OSError:
        return "unknown"


def parse_value(text):
    for msg, name in EXCEPTIONS.items():
        if text.startswith(msg):
            return {"type": name}
    if text == '""':
        return {"type": "STRING", "value": "", "hex": ""}
    m = re.match(r"^([A-Za-z0-9-]+): ?(.*)$", text, re.S)
    if not m:
        return {"type": "unknown", "value": text}
    typ, val = m.group(1), m.group(2)
    out = {"type": typ, "value": val}
    if typ == "Hex-STRING":
        out["hex"] = val.replace(" ", "").replace("\n", "").lower()
    elif typ == "Timeticks":
        t = re.match(r"^\((\d+)\)", val)
        if t:
            out["value"] = t.group(1)
    elif typ == "STRING":
        s = val[1:-1] if val.startswith('"') and val.endswith('"') else val
        out["hex"] = s.encode().hex()
    return out


def parse(stdout):
    binds, cur = [], None
    for line in stdout.splitlines():
        m = LINE.match(line)
        if m:
            cur = {"oid": m.group(1).lstrip(".")}
            cur.update(parse_value(m.group(2)))
            binds.append(cur)
        elif cur is not None and cur.get("type") == "Hex-STRING":
            # Long hex strings continue on the next lines.
            cur["value"] += " " + line.strip()
            cur["hex"] += line.replace(" ", "").lower()
    return binds


def main(argv):
    if argv[:1] == ["version"]:
        print("net-snmp", version())
        return 0
    if argv[:1] == ["print-capabilities"]:
        json.dump({"schemaVersion": "1.0", "adapter": "netsnmp", "implementation": "Net-SNMP", "version": version(),
                   "license": "Net-SNMP (BSD-style)", "roles": ["snmp-manager"],
                   "features": {"versions": ["1", "2c"], "operations": sorted(TOOLS), "mibs": False}}, sys.stdout)
        print()
        return 0
    if len(argv) < 2 or argv[0] != "snmp" or argv[1] not in TOOLS:
        print("usage: profinet-interop snmp get|getnext|bulkget|walk|bulkwalk|set --host IP [flags] OID...", file=sys.stderr)
        return 2
    op, rest = argv[1], argv[2:]
    host, port, community, ver = "", "161", "public", "2c"
    timeout, retries, maxrep, nonrep = "2", "1", None, None
    oids, setargs = [], []
    i = 0
    while i < len(rest):
        a = rest[i]
        val = rest[i + 1] if i + 1 < len(rest) else None
        if a in ("--host", "--port", "--community", "--version", "--timeout", "--retries", "--max-rep", "--non-rep") and val is None:
            print(f"{a} needs a value", file=sys.stderr)
            return 2
        if a == "--host":
            host = val
        elif a == "--port":
            port = val
        elif a == "--community":
            community = val
        elif a == "--version":
            ver = val
        elif a == "--timeout":
            timeout = val
        elif a == "--retries":
            retries = val
        elif a == "--max-rep":
            maxrep = val
        elif a == "--non-rep":
            nonrep = val
        elif a == "--set":
            if i + 3 >= len(rest):
                print("--set needs OID TYPE VALUE", file=sys.stderr)
                return 2
            setargs += rest[i + 1:i + 4]
            i += 4
            continue
        elif a.startswith("--"):
            print(f"unknown flag {a}", file=sys.stderr)
            return 2
        else:
            oids.append(a)
            i += 1
            continue
        i += 2
    if not host or ver not in ("1", "2c") or (op == "set") != bool(setargs) or (op != "set" and not oids and op not in ("walk", "bulkwalk")):
        print("usage: --host is required, --version 1 or 2c, OIDs (set: --set OID TYPE VALUE)", file=sys.stderr)
        return 2
    cmd = [TOOLS[op], "-v", ver, "-c", community, "-t", timeout, "-r", retries, "-On", "-Ox", "-Oe", "-m", "",
           f"udp:{host}:{port}"]
    if op in ("bulkget", "bulkwalk"):
        if maxrep is not None:
            cmd[1:1] = [f"-Cr{maxrep}"]
        if nonrep is not None and op == "bulkget":
            cmd[1:1] = [f"-Cn{nonrep}"]
    cmd += oids + setargs
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    out = {"schemaVersion": "1.0", "adapter": "netsnmp", "op": op, "command": cmd, "exit": p.returncode,
           "varbinds": parse(p.stdout)}
    err = p.stderr.strip()
    if err:
        out["stderr"] = err
    m = re.search(r"Reason: \(?([A-Za-z]+)\)?", p.stdout + "\n" + err)
    if m:
        out["errorStatus"] = m.group(1)
    m = re.search(r"Failed object: (\.?[0-9.]+)", p.stdout + "\n" + err)
    if m:
        out["failedObject"] = m.group(1).lstrip(".")
    if "Timeout: No Response" in err:
        out["timeout"] = True
    if "OID not increasing" in err:
        out["notIncreasing"] = True
    out["ok"] = p.returncode == 0 and "errorStatus" not in out and not out.get("timeout")
    json.dump(out, sys.stdout)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
