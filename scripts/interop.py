#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Cross-stack self-test: the given adapters against each other on Layer 2.

    interop.py <adapter> <adapter>...

Every case runs for every pair of the given adapters with the roles it needs
(tests/cases.tsv): a DCP tool against an IO-Device, an IO-Controller against
an IO-Device, an adapter against itself too. Each pair gets its own Docker
bridge network; the containers have CAP_NET_RAW and CAP_NET_ADMIN and a
static IPv4 address, as the contract says (docs/CONTAINER_CONTRACT.md). The
script knows how to drive the adapters below; another adapter with a role is
reported as not tested for it. MRP rings, decoders and SNMP stay with
the consumers' interop suites, the behavioural tests of the harness.

Images: scripts/lib.sh's rule, ADAPTER_IMAGE_<adapter> (a dash is an
underscore) or the local build profinet-interop-<adapter>:$TAG (default dev).

Writes REPORT_DIR/results.json (interop-result-v1; an image whose
capability document says upstream.independentEngine false is recorded as
not independent) and prints one "[interop]" line per result. The exit
status is 1 when a result is fail or infra-error (interop_result.py's rule).

GATE=<adapter> names the implementation under test: only the pairs that
involve it run (an adapter against itself too), and the document's gate is
set. Without it every pair runs.
"""

import json
import os
import random
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import interop_result  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES = os.path.join(ROOT, "tests", "cases.tsv")

# The drivers: which roles of which adapter this script can run.
DCP_TOOLS = ("otfabric", "pnio-dcp")
DEVICES = ("otfabric", "pnio-rs", "pnet")
CONTROLLERS = ("otfabric", "profinet-py")


def image_of(adapter):
    v = os.environ.get("ADAPTER_IMAGE_" + adapter.replace("-", "_"))
    return v or "profinet-interop-%s:%s" % (adapter, os.environ.get("TAG", "dev"))


def log(msg):
    print("[interop] " + msg, file=sys.stderr, flush=True)


def docker(*args, timeout=180, check=True):
    p = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)
    if check and p.returncode != 0:
        raise RuntimeError("docker %s: exit %d: %s" % (" ".join(args[:3]), p.returncode, p.stderr.strip()[-400:]))
    return p


def json_lines(text):
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


class Net:
    """One Docker bridge network with a shared directory, for one pair."""

    def __init__(self, run_id, n):
        self.name = "pni-%s-%d" % (run_id, n)
        self.share = tempfile.mkdtemp(prefix="profinet-interop-")
        os.chmod(self.share, 0o777)
        self.containers = []
        last = None
        for _ in range(20):
            self.octet = random.randint(16, 250)
            p = docker("network", "create", "--driver", "bridge", "--subnet", "10.%d.%d.0/24" % (self.octet, n % 250),
                       self.name, check=False)
            if p.returncode == 0:
                self.prefix = "10.%d.%d." % (self.octet, n % 250)
                return
            last = p.stderr
        raise RuntimeError("no free subnet for %s: %s" % (self.name, last))

    def args(self, cname, host):
        return ["--name", cname, "--network", self.name, "--ip", self.prefix + str(host),
                "--cap-add", "NET_RAW", "--cap-add", "NET_ADMIN", "-v", self.share + ":/share",
                "--label", "profinet-interop.run=" + self.name]

    def start(self, adapter, role, host, *cmd):
        cname = "%s-%s-%s" % (self.name, role, adapter)
        docker("run", "-d", *self.args(cname, host), image_of(adapter), *cmd)
        self.containers.append(cname)
        return cname

    def run(self, adapter, role, host, *cmd, timeout=180):
        cname = "%s-%s-%s" % (self.name, role, adapter)
        p = docker("run", "--rm", *self.args(cname, host), image_of(adapter), *cmd, timeout=timeout, check=False)
        return p.returncode, p.stdout, p.stderr

    def logs(self, cname):
        return docker("logs", cname, check=False).stdout

    def wait_event(self, cname, pred, timeout=60):
        deadline = time.time() + timeout
        while time.time() < deadline:
            for ev in json_lines(self.logs(cname)):
                if pred(ev):
                    return ev
            state = docker("inspect", "-f", "{{.State.Status}}", cname, check=False).stdout.strip()
            if state != "running":
                raise RuntimeError("%s is %s: %s" % (cname, state, self.logs(cname)[-400:]))
            time.sleep(0.3)
        raise RuntimeError("%s: no ready event in %ds: %s" % (cname, timeout, self.logs(cname)[-400:]))

    def close(self):
        for c in self.containers:
            docker("rm", "-f", c, check=False)
        docker("network", "rm", self.name, check=False)


# ── IO-Device drivers ─────────────────────────────────────────────────────────

def start_device(net, adapter, station):
    """Starts the device; returns (container, mac, gsdml path in /share or None)."""
    if adapter == "otfabric":
        c = net.start(adapter, "dev", 30, "device", "--station", station, "--gsdml-out", "/share/%s.xml" % station)
        ev = net.wait_event(c, lambda e: e.get("event") == "start")
        return c, ev["mac"], "/share/%s.xml" % station
    if adapter == "pnio-rs":
        p = docker("run", "--rm", image_of(adapter), "print-gsdml")
        with open(os.path.join(net.share, station + ".xml"), "w") as f:
            f.write(p.stdout)
        c = net.start(adapter, "dev", 30, "device", "--station", station)
        ev = net.wait_event(c, lambda e: e.get("event") == "start")
        net.wait_event(c, lambda e: e.get("event") == "ar-state")
        return c, ev["mac"], "/share/%s.xml" % station
    if adapter == "pnet":
        c = net.start(adapter, "dev", 30, "device", "--station", station)
        ev = net.wait_event(c, lambda e: e.get("event") == "start")
        time.sleep(2)
        return c, ev["mac"], None
    raise KeyError(adapter)


# ── DCP tool drivers ──────────────────────────────────────────────────────────

def norm_mac(m):
    return str(m).lower().replace("-", ":")


def dcp_identify(net, tool, station):
    """The (name, mac) pairs that answered an Identify All."""
    if tool == "otfabric":
        code, out, err = net.run(tool, "dcp", 3, "dcp", "-wait", "3s", "identify")
        docs = [d for d in json_lines(out) if d.get("event") == "dcp"]
        if not docs:
            raise RuntimeError("otfabric dcp identify: exit %d: %s %s" % (code, out[-300:], err[-300:]))
        return [(d.get("nameOfStation", ""), norm_mac(d.get("mac"))) for d in docs[-1].get("devices") or []]
    code, out, err = net.run(tool, "dcp", 3, "dcp", "identify-all", "--timeout", "3")
    d = (json_lines(out) or [{}])[-1]
    if not d.get("ok"):
        raise RuntimeError("pnio-dcp identify-all: %s %s" % (out[-300:], err[-300:]))
    return [(x.get("name", ""), norm_mac(x.get("mac"))) for x in d.get("devices") or []]


def dcp_get_name(net, tool, mac):
    if tool == "otfabric":
        code, out, err = net.run(tool, "dcp", 3, "dcp", "-mac", mac, "get")
        d = (json_lines(out) or [{}])[-1]
        if d.get("error") or code:
            raise RuntimeError("otfabric dcp get: %s %s" % (out[-300:], err[-300:]))
        return (d.get("identity") or {}).get("nameOfStation")
    code, out, err = net.run(tool, "dcp", 3, "dcp", "get-name", "--mac", mac)
    d = (json_lines(out) or [{}])[-1]
    return d.get("value")


def dcp_set_name(net, tool, mac, name):
    """Sets the name temporarily; returns an error string or None."""
    if tool == "otfabric":
        code, out, err = net.run(tool, "dcp", 3, "dcp", "-mac", mac, "set-name", name)
        d = (json_lines(out) or [{}])[-1]
        return d.get("error") or (("exit %d: %s" % (code, err[-300:])) if code else None)
    code, out, err = net.run(tool, "dcp", 3, "dcp", "set-name", "--mac", mac, name, "--temporary")
    d = (json_lines(out) or [{}])[-1]
    return None if d.get("code") == 0 else "pnio-dcp set-name: %s" % (out[-300:] or err[-300:])


# ── IO-Controller drivers ─────────────────────────────────────────────────────

def connect(net, ctrl, station, gsdml):
    """Runs one AR: returns {"connected", "cyclic", "im0", "error"}."""
    if ctrl == "otfabric":
        code, out, err = net.run(ctrl, "ctrl", 2, "controller", "--station", station, "--model", gsdml, "--advanced",
                                 "--im0", "--duration", "3s", "--timeout", "30s", timeout=120)
        r = [d for d in json_lines(out) if d.get("event") == "report"]
        if not r:
            return {"connected": False, "error": "no report: exit %d: %s %s" % (code, out[-300:], err[-300:])}
        r = r[-1]
        inputs = r.get("inputs") or {}
        good = [v for v in inputs.values() if isinstance(v, dict) and v.get("data")]
        im0 = r.get("im0") or {}
        return {"connected": r.get("running") is True, "cyclic": bool(good) and len(good) == len(inputs),
                "im0": bool(im0.get("OrderID")), "error": r.get("error") or r.get("lastError") or r.get("im0Error")}
    code, out, err = net.run(ctrl, "ctrl", 2, "controller", "--station", station, "--gsdml", gsdml, "--duration", "3",
                             timeout=180)
    docs = json_lines(out)
    if not docs or "steps" not in docs[-1]:
        return {"connected": False, "error": "no report: exit %d: %s %s" % (code, out[-300:], err[-300:])}
    steps = {s["step"]: s for s in docs[-1]["steps"]}
    ok = lambda name: bool(steps.get(name, {}).get("ok"))  # noqa: E731
    failed = [("%s: %s" % (k, v.get("error"))) for k, v in steps.items() if not v.get("ok")]
    return {"connected": ok("start-cyclic"), "cyclic": ok("start-cyclic") and ok("cyclic-stats"), "im0": ok("read-im0"),
            "error": "; ".join(failed)[:400] or None}


# ── Cases ─────────────────────────────────────────────────────────────────────

def load_cases():
    cases = []
    with open(CASES) as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            cid, client, server, feature, title = line.rstrip("\n").split("\t")
            cases.append({"id": cid, "client": client, "server": server, "feature": feature, "title": title})
    return cases


def capabilities(adapter):
    p = docker("run", "--rm", image_of(adapter), "print-capabilities", check=False)
    if p.returncode != 0:
        raise RuntimeError("%s: print-capabilities: %s" % (adapter, p.stderr.strip()))
    return json.loads(p.stdout)


def main(argv):
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    adapters = list(dict.fromkeys(argv))
    report_dir = os.environ.get("REPORT_DIR", os.path.join(ROOT, "reports"))
    os.makedirs(report_dir, exist_ok=True)
    started = interop_result.now()
    caps = {a: capabilities(a) for a in adapters}
    cases = load_cases()
    results = []
    run_id = "%x" % (os.getpid() & 0xFFFF)
    n = 0

    def add(case, client, server, outcome, reason, t0):
        r = {"id": "%s.%s.%s" % (case["id"], client, server), "title": case["title"], "suite": "interop",
             "feature": case["feature"], "roles": {case["client"]: client, case["server"]: server},
             "outcome": outcome, "durationMs": int((time.time() - t0) * 1000)}
        if reason:
            r["reason"] = reason
        results.append(r)
        log("%-16s %s %s -> %s%s" % (outcome, case["id"], client, server, (": " + reason) if reason and outcome != "pass" else ""))

    gate = os.environ.get("GATE")

    def wanted(a, b):
        return not gate or gate in (a, b)

    def has(a, role):
        return role in caps[a].get("roles", [])

    def feat(a, name):
        return caps[a].get("features", {}).get(name) is True

    dcp_cases = [c for c in cases if c["client"] == "dcp-tool"]
    ar_cases = [c for c in cases if c["client"] == "controller"]
    for tool in [a for a in adapters if has(a, "dcp-tool")]:
        for dev in [a for a in adapters if has(a, "device") and wanted(tool, a)]:
            if tool not in DCP_TOOLS or dev not in DEVICES:
                for c in dcp_cases:
                    add(c, tool, dev, "not-tested", "interop.py has no driver for this pair", time.time())
                continue
            n += 1
            t0 = time.time()
            net = None
            try:
                net = Net(run_id, n)
                station = "pni-dut"
                _, mac, _ = start_device(net, dev, station)
                mac = norm_mac(mac)
                for c in dcp_cases:
                    t0 = time.time()
                    if c["feature"] == "dcpSetName" and not (feat(dev, "dcpSetName") and feat(dev, "dcpGet")):
                        add(c, tool, dev, "unsupported", "the device declares no DCP Set/Get NameOfStation", t0)
                        continue
                    if c["feature"] == "dcpGet" and not feat(dev, "dcpGet"):
                        add(c, tool, dev, "unsupported", "the device declares no DCP Get", t0)
                        continue
                    try:
                        if c["feature"] == "dcpIdentify":
                            found = dcp_identify(net, tool, station)
                            ok = (station, mac) in found
                            add(c, tool, dev, "pass" if ok else "fail", None if ok else "want %s %s in %s" % (station, mac, found), t0)
                        elif c["feature"] == "dcpGet":
                            got = dcp_get_name(net, tool, mac)
                            add(c, tool, dev, "pass" if got == station else "fail", None if got == station else "name %r, want %r" % (got, station), t0)
                        elif c["feature"] == "dcpSetName":
                            err = dcp_set_name(net, tool, mac, "pni-renamed")
                            got = None if err else dcp_get_name(net, tool, mac)
                            ok = err is None and got == "pni-renamed"
                            add(c, tool, dev, "pass" if ok else "fail", None if ok else (err or "name after Set %r" % got), t0)
                            if ok:
                                dcp_set_name(net, tool, mac, station)
                    except Exception as e:  # noqa: BLE001
                        add(c, tool, dev, "fail", str(e)[:400], t0)
            except Exception as e:  # noqa: BLE001
                for c in dcp_cases:
                    add(c, tool, dev, "infra-error", str(e)[:400], t0)
            finally:
                if net:
                    net.close()
    for ctrl in [a for a in adapters if has(a, "controller")]:
        for dev in [a for a in adapters if has(a, "device") and wanted(ctrl, a)]:
            if ctrl not in CONTROLLERS or dev not in DEVICES:
                for c in ar_cases:
                    add(c, ctrl, dev, "not-tested", "interop.py has no driver for this pair", time.time())
                continue
            n += 1
            t0 = time.time()
            net = None
            try:
                net = Net(run_id, n)
                station = "pni-dut"
                _, _, gsdml = start_device(net, dev, station)
                if gsdml is None:
                    for c in ar_cases:
                        add(c, ctrl, dev, "not-tested", "the device's adapter offers no GSDML", t0)
                    continue
                r = connect(net, ctrl, station, gsdml)
                for c in ar_cases:
                    key = {"connect": "connected", "cyclic": "cyclic", "im0": "im0"}[c["feature"]]
                    ok = bool(r.get(key))
                    add(c, ctrl, dev, "pass" if ok else "fail", None if ok else (r.get("error") or "%s not reached" % key), t0)
            except Exception as e:  # noqa: BLE001
                for c in ar_cases:
                    add(c, ctrl, dev, "infra-error", str(e)[:400], t0)
            finally:
                if net:
                    net.close()

    impls = []
    for a in adapters:
        up = caps[a].get("upstream") or {}
        i = {"name": a, "version": str(up.get("version") or caps[a].get("version") or "unrecorded"),
             "independent": up.get("independentEngine", True) is not False}
        if up.get("name"):
            i["upstream"] = up["name"]
        if up.get("revision"):
            i["revision"] = up["revision"]
        if caps[a].get("license"):
            i["license"] = caps[a]["license"]
        digest = interop_result.repo_digest(image_of(a))
        if digest:
            i["image"] = digest
        impls.append(i)
    doc = {"schemaVersion": "1.0", "repository": "otfabric/profinet-interop",
           "interopVersion": interop_result.version_field(ROOT, "interop_version"),
           "contractVersion": interop_result.version_field(ROOT, "contract_version"),
           "gitSha": interop_result.git_sha(ROOT), "startedAt": started, "finishedAt": interop_result.now(),
           "host": interop_result.host(), "implementations": impls, "results": results,
           "reproduce": ("GATE=%s " % gate if gate else "") + "scripts/interop.sh " + " ".join(adapters)}
    if gate:
        doc["gate"] = gate
    path = os.path.join(report_dir, "results.json")
    interop_result.write(path, doc)
    s = doc["summary"]
    print("[interop] %d pass, %d fail, %d unsupported, %d not-tested, %d infra-error: %s" % (
        s["pass"], s["fail"], s["unsupported"], s["not-tested"], s["infra-error"], path))
    bad = interop_result.problems(doc)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
