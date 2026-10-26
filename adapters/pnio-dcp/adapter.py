"""profinet-interop adapter for pnio-dcp (a DCP client).

  profinet-interop dcp identify-all [--timeout S]
  profinet-interop dcp identify --mac MAC
  profinet-interop dcp get-name|get-ip --mac MAC
  profinet-interop dcp set-name --mac MAC NAME [--temporary]
  profinet-interop dcp set-ip --mac MAC IP MASK GW [--temporary]
  profinet-interop dcp blink|reset --mac MAC
  profinet-interop print-capabilities | version

Each command prints one JSON document (docs/CONTAINER_CONTRACT.md).
pnio-dcp selects the interface by its IP address, which the adapter reads
from the interface given with --iface.
"""

import argparse
import importlib.metadata
import json
import socket
import sys
import traceback

import psutil

VERSION = importlib.metadata.version("pnio-dcp")


def own_ip(iface):
    for a in psutil.net_if_addrs().get(iface, []):
        if a.family == socket.AF_INET:
            return a.address
    raise SystemExit(f"no IPv4 address on {iface}")


def dev_doc(d):
    return {"name": d.name_of_station, "mac": d.MAC, "ip": d.IP, "mask": d.netmask, "gateway": d.gateway, "family": d.family}


def main():
    p = argparse.ArgumentParser(prog="profinet-interop")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dcp")
    d.add_argument("op")
    d.add_argument("value", nargs="*")
    d.add_argument("--iface", default="eth0")
    d.add_argument("--mac")
    d.add_argument("--timeout", type=float, default=3)
    d.add_argument("--temporary", action="store_true")
    sub.add_parser("print-capabilities")
    sub.add_parser("version")
    a = p.parse_args()
    if a.cmd == "version":
        print("pnio-dcp", VERSION)
        return 0
    if a.cmd == "print-capabilities":
        json.dump({"schemaVersion": "1.0", "adapter": "pnio-dcp", "implementation": "pnio-dcp", "version": VERSION, "license": "MIT",
                   "roles": ["dcp-tool"], "features": {"dcpIdentify": True, "dcpGet": True, "dcpSetName": True, "dcpSetIP": True,
                                                       "dcpSignal": True, "dcpReset": True}}, sys.stdout)
        print()
        return 0
    import pnio_dcp

    doc = {"schemaVersion": "1.0", "adapter": "pnio-dcp", "version": VERSION, "op": a.op}
    try:
        dcp = pnio_dcp.DCP(own_ip(a.iface))
        perm = not a.temporary
        if a.op == "identify-all":
            doc["devices"] = [dev_doc(x) for x in dcp.identify_all(timeout=a.timeout)]
        elif a.op == "identify":
            doc["device"] = dev_doc(dcp.identify(a.mac))
        elif a.op == "get-name":
            doc["value"] = dcp.get_name_of_station(a.mac)
        elif a.op == "get-ip":
            doc["value"] = dcp.get_ip_address(a.mac)
        elif a.op == "set-name":
            r = dcp.set_name_of_station(a.mac, a.value[0], store_permanent=perm)
            doc["code"], doc["message"] = int(r.code), r.get_message()
        elif a.op == "set-ip":
            r = dcp.set_ip_address(a.mac, a.value[:3], store_permanent=perm)
            doc["code"], doc["message"] = int(r.code), r.get_message()
        elif a.op == "blink":
            r = dcp.blink(a.mac)
            doc["code"], doc["message"] = int(r.code), r.get_message()
        elif a.op == "reset":
            r = dcp.reset_to_factory(a.mac)
            doc["code"], doc["message"] = int(r.code), r.get_message()
        else:
            print(f"unknown operation {a.op}", file=sys.stderr)
            return 2
        doc["ok"] = True
    except Exception as e:  # noqa: BLE001 - a failure is a result
        doc["ok"] = False
        doc["error"] = f"{type(e).__name__}: {e}"
        doc["trace"] = traceback.format_exc(limit=3)
    json.dump(doc, sys.stdout, default=str)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
