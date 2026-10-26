"""profinet-interop adapter for scapy: decode a pcap with scapy's PROFINET
layers and report, per protocol, how many frames decoded into structured
layers, the frames that did not, and the fields of the DCP and RPC frames.

  profinet-interop decode FILE.pcap
  profinet-interop print-capabilities | version
"""

import json
import sys
from collections import Counter

import scapy
from scapy.all import Ether, Raw, rdpcap  # noqa: F401
from scapy.contrib import pnio, pnio_dcp, pnio_rpc  # noqa: F401
from scapy.layers.dcerpc import DceRpc4
from scapy.layers.inet import UDP
from scapy.packet import bind_layers

# PNIO's RPC endpoint: scapy binds DCE/RPC to it only on request.
bind_layers(UDP, DceRpc4, dport=34964)
bind_layers(UDP, DceRpc4, sport=34964)


def classify(pkt):
    names = []
    layer = pkt
    while layer:
        names.append(layer.__class__.__name__)
        layer = layer.payload if layer.payload and layer.payload.__class__.__name__ != "NoPayload" else None
    return names


def frame_id(raw):
    b = bytes(raw)
    off = 12
    if b[12:14] == b"\x81\x00":
        off = 16
    if b[off:off + 2] != b"\x88\x92":
        return None
    return int.from_bytes(b[off + 2:off + 4], "big")


def kind(fid):
    if fid is None:
        return None
    if 0xFEFC <= fid <= 0xFEFF:
        return "dcp"
    if fid in (0xFC01, 0xFE01):
        return "alarm"
    if 0x8000 <= fid <= 0xFBFF:
        return "rt"
    return "other"


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "version":
        print("scapy", scapy.VERSION)
        return 0
    if len(sys.argv) == 2 and sys.argv[1] == "print-capabilities":
        json.dump({"schemaVersion": "1.0", "adapter": "scapy", "implementation": "scapy", "version": scapy.VERSION,
                   "license": "GPL-2.0-only", "roles": ["decoder"]}, sys.stdout)
        print()
        return 0
    if len(sys.argv) != 3 or sys.argv[1] != "decode":
        print("usage: profinet-interop decode FILE.pcap | print-capabilities | version", file=sys.stderr)
        return 2
    pkts = rdpcap(sys.argv[2])
    stats = Counter()
    undecoded = []
    dcp = []
    rpc = Counter()
    for i, p in enumerate(pkts, 1):
        names = classify(p)
        fid = frame_id(p)
        k = kind(fid) or ("udp" if "UDP" in names else names[1] if len(names) > 1 else names[0])
        stats[k] += 1
        structured = [n for n in names if n not in ("Ether", "Dot1Q", "Raw", "Padding", "IP", "UDP")]
        if k in ("dcp", "rt", "alarm") and not structured:
            undecoded.append({"frame": i, "kind": k, "frameId": hex(fid), "layers": names})
        if k == "dcp" and "ProfinetDCP" in names:
            d = p["ProfinetDCP"]
            dcp.append({"frame": i, "service": int(d.service_id), "type": int(d.service_type), "xid": int(d.xid)})
        if "DceRpc4" in names:
            r = p["DceRpc4"]
            rpc[f"ptype={int(r.ptype)} opnum={int(r.opnum)}"] += 1
            if not any(n.startswith("PNIO") or n.startswith("IOD") or n.startswith("AR") for n in names):
                undecoded.append({"frame": i, "kind": "rpc", "layers": names})
    json.dump({"schemaVersion": "1.0", "adapter": "scapy", "version": scapy.VERSION, "frames": len(pkts), "byKind": stats,
               "rpc": rpc, "dcp": dcp[:50], "undecoded": undecoded[:100], "undecodedCount": len(undecoded)}, sys.stdout)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
