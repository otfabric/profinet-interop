"""profinet-interop adapter for profinet-py (an IO-Controller and DCP tool).

Every command prints one JSON document on stdout (see
docs/CONTAINER_CONTRACT.md); each step of a scenario reports ok, the value
it read and the error it met, so that the harness can tell a failing step
from one the implementation does not support.

  profinet-interop controller --station NAME [--iface eth0] [--gsdml FILE] [--reparam S:SS:IDX:HEX]...
                  [--duration S] [--output SLOT:SUBSLOT:HEX]...
  profinet-interop dcp identify|get|set-name|set-ip|signal|reset
                  [--iface eth0] [--mac MAC] [--station NAME] [VALUE...]
  profinet-interop print-capabilities
  profinet-interop version
"""

import argparse
import importlib.metadata
import json
import sys
import time
import traceback

VERSION = importlib.metadata.version("profinet-py")


def emit(doc):
    json.dump(doc, sys.stdout, default=str)
    sys.stdout.write("\n")
    sys.stdout.flush()


def step(report, name, fn):
    """Run one step, recording its result; never raise."""
    entry = {"step": name}
    try:
        v = fn()
        entry["ok"] = True
        if v is not None:
            entry["value"] = v
    except Exception as e:  # noqa: BLE001 - every failure is a result
        entry["ok"] = False
        entry["error"] = f"{type(e).__name__}: {e}"
        entry["trace"] = traceback.format_exc(limit=3)
    report["steps"].append(entry)
    return entry


def hexb(b):
    return b.hex() if isinstance(b, (bytes, bytearray)) else b


def controller(args):
    from profinet import ProfinetDevice
    from profinet.gsdml import load_gsdml

    report = {"schemaVersion": "1.0", "adapter": "profinet-py", "version": VERSION, "station": args.station, "steps": []}
    dev = None
    found = step(report, "discover", lambda: ProfinetDevice.discover(args.station, args.iface, timeout=args.timeout))
    if not found["ok"]:
        emit(report)
        return 0
    dev = found.pop("value")
    found["value"] = {"name": dev.name, "ip": dev.ip, "mac": dev.mac}

    def im0():
        r = dev.read_im0()
        return {"vendorId": r.vendor_id, "orderId": r.order_id.strip(), "serial": r.im_serial_number.strip(),
                "hardwareRevision": r.im_hardware_revision}

    step(report, "read-im0", im0)
    step(report, "write-im1", lambda: dev.write_im1(tag_function="interop function", tag_location="interop location"))

    def im1():
        r = dev.read_im1()
        return {"tagFunction": r.im_tag_function.strip(), "tagLocation": r.im_tag_location.strip()}

    step(report, "read-im1", im1)
    step(report, "read-im2", lambda: str(dev.read_im2()))
    step(report, "read-im3", lambda: str(dev.read_im3()))
    step(report, "read-im4", lambda: str(dev.read_im4()))
    step(report, "write-record", lambda: dev.write(slot=2, subslot=1, index=0x0010, data=b"\x00\x05"))
    step(report, "read-record", lambda: hexb(dev.read(slot=2, subslot=1, index=0x0010)))
    step(report, "read-implicit-im0", lambda: hexb(dev.read_implicit(slot=0, subslot=1, index=0xAFF0)))
    step(report, "read-invalid-index", lambda: hexb(dev.read(slot=1, subslot=1, index=0x7777)))
    step(report, "module-diff", lambda: str(dev.read_module_diff()))
    step(report, "diagnosis", lambda: str(dev.read_all_diagnosis()))
    step(report, "discover-slots", lambda: [str(s) for s in dev.discover_slots()])
    if args.gsdml:
        alarms = []
        dev.on_alarm(lambda a: alarms.append(str(a)))
        cyc = {}

        def start():
            from profinet import IOCRSetup

            g = load_gsdml(args.gsdml)
            slots = g.build_io_slots()
            setup = IOCRSetup(slots=slots, reduction_ratio=args.rr)
            cyc["c"] = dev.start_cyclic(setup)
            return [{"slot": s.slot, "subslot": s.subslot, "in": s.input_length, "out": s.output_length} for s in slots]

        if step(report, "start-cyclic", start)["ok"]:
            c = cyc["c"]
            for o in args.output:
                slot, sub, data = o.split(":")
                step(report, f"set-output {slot}:{sub}", lambda s=int(slot), u=int(sub), d=bytes.fromhex(data): c.set_output_data(s, u, d))
            time.sleep(args.duration)
            if args.reparam:
                # Re-parameterization of the running AR with profinet-py's
                # own control calls: PrmBegin, the writes, PrmEnd, then
                # the device's ApplicationReady, answered.
                rpc = dev._rpc
                step(report, "prm-begin", lambda: hexb(rpc.prm_begin()))
                for w in args.reparam:
                    slot, sub, idx, data = w.split(":")
                    step(report, f"reparam-write {slot}:{sub}:{idx}",
                         lambda s=int(slot), u=int(sub), i=int(idx, 0), d=bytes.fromhex(data): rpc.write(api=0, slot=s, subslot=u, idx=i, data=d))
                step(report, "prm-end", lambda: hexb(rpc.prm_end()))
                step(report, "reparam-application-ready", lambda: hexb(rpc.application_ready(timeout=10)))
                time.sleep(1)
            inputs = {}
            for s in c._input_iocr.slots if hasattr(c, "_input_iocr") else []:
                pass
            for key in args.read_input:
                slot, sub = key.split(":")
                step(report, f"input {slot}:{sub}", lambda s=int(slot), u=int(sub): hexb(c.get_input_data(s, u)))
            step(report, "cyclic-stats", lambda: {k: v for k, v in vars(c.stats).items()} if hasattr(c, "stats") and hasattr(c.stats, "__dict__") else str(getattr(c, "stats", None)))
            step(report, "stop-cyclic", c.stop)
        report["alarms"] = alarms
    step(report, "close", dev.close)
    emit(report)
    return 0


def dcp_cmd(args):
    from profinet import dcp
    from profinet.util import ethernet_socket, get_mac

    report = {"schemaVersion": "1.0", "adapter": "profinet-py", "version": VERSION, "op": args.op, "steps": []}
    sock = ethernet_socket(args.iface, 0x8892)
    src = get_mac(args.iface)

    def target():
        if args.mac:
            return args.mac
        for d in dcp.send_discover(sock, src) and dcp.read_response(sock, src, timeout_sec=3) or []:
            if getattr(d, "name", None) == args.station:
                return d.mac
        raise LookupError(f"station {args.station} not found")

    if args.op == "identify":

        def identify():
            dcp.send_discover(sock, src)
            out = []
            # read_response maps each responder's MAC to its blocks.
            for mac, blocks in dcp.read_response(sock, src, timeout_sec=args.timeout).items():
                d = dcp.DCPDeviceDescription(mac, blocks)
                out.append({"name": d.name, "mac": d.mac, "ip": d.ip, "vendorId": d.vendor_high << 8 | d.vendor_low, "deviceId": d.device_high << 8 | d.device_low})
            return out

        step(report, "identify", identify)
    elif args.op == "get":
        step(report, "get-name", lambda: hexb(dcp.get_param(sock, src, target(), "name")))
        step(report, "get-ip", lambda: hexb(dcp.get_param(sock, src, target(), "ip")))
    elif args.op == "set-name":
        step(report, "set-name", lambda: dcp.set_param(sock, src, target(), "name", args.value[0], permanent=args.permanent))
    elif args.op == "set-ip":
        ip, mask, gw = args.value
        step(report, "set-ip", lambda: dcp.set_ip(sock, src, target(), ip, mask, gw, permanent=args.permanent))
    elif args.op == "signal":
        step(report, "signal", lambda: dcp.signal_device(sock, src, target()))
    elif args.op == "reset":
        step(report, "reset", lambda: dcp.reset_to_factory(sock, src, target()))
    else:
        print(f"unknown operation {args.op}", file=sys.stderr)
        return 2
    emit(report)
    return 0


def main():
    p = argparse.ArgumentParser(prog="profinet-interop")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("controller")
    c.add_argument("--iface", default="eth0")
    c.add_argument("--station", required=True)
    c.add_argument("--gsdml")
    c.add_argument("--duration", type=float, default=3.0)
    c.add_argument("--rr", type=int, default=32)
    c.add_argument("--timeout", type=float, default=10.0)
    c.add_argument("--output", action="append", default=[])
    c.add_argument("--read-input", action="append", default=[])
    c.add_argument("--reparam", action="append", default=[], help="SLOT:SUBSLOT:INDEX:HEX written between PrmBegin and PrmEnd once cyclic IO runs")
    d = sub.add_parser("dcp")
    d.add_argument("op")
    d.add_argument("value", nargs="*")
    d.add_argument("--iface", default="eth0")
    d.add_argument("--mac")
    d.add_argument("--station")
    d.add_argument("--permanent", action="store_true")
    d.add_argument("--timeout", type=int, default=3)
    sub.add_parser("print-capabilities")
    sub.add_parser("version")
    a = p.parse_args()
    if a.cmd == "controller":
        return controller(a)
    if a.cmd == "dcp":
        return dcp_cmd(a)
    if a.cmd == "version":
        print("profinet-py", VERSION)
        return 0
    emit({"schemaVersion": "1.0", "adapter": "profinet-py", "implementation": "profinet-py", "version": VERSION,
          "license": "GPL-3.0-only", "roles": ["controller", "dcp-tool"],
          "features": {"dcpIdentify": True, "dcpGet": True, "dcpSetName": True, "dcpSetIP": True, "dcpSignal": True, "dcpReset": True,
                       "connect": True, "iosar": True, "readWrite": True, "readImplicit": True, "im0to4": True, "diagnosisRecords": True,
                       "moduleDiff": True, "rtClass1Legacy": True, "alarms": True, "lldp": False, "gsdml": True}})
    return 0


if __name__ == "__main__":
    sys.exit(main())
