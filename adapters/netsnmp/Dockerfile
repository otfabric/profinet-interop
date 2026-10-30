# syntax=docker/dockerfile:1
# Net-SNMP's command-line manager (snmpget, snmpgetnext, snmpbulkget,
# snmpwalk, snmpbulkwalk, snmpset; BSD-style licences) from the Debian
# bookworm package "snmp", driven by adapter.py. Debian's package has no
# IETF MIB files: every OID is numeric (-On) and no MIB is loaded. Pinned
# by Debian, like tshark: versions.yaml records the version.
FROM debian:bookworm-20251020-slim@sha256:78d2f66e0fec9e5a39fb2c72ea5e052b548df75602b5215ed01a17171529f706
RUN apt-get update && apt-get install -y --no-install-recommends snmp python3 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /licenses/net-snmp && cp /usr/share/doc/libsnmp40/copyright /licenses/net-snmp/copyright \
    && dpkg-query -W -f='${Version}\n' snmp > /licenses/net-snmp/VERSION
COPY adapter.py /usr/local/lib/profinet-interop/adapter.py
RUN printf '#!/bin/sh\nexec python3 /usr/local/lib/profinet-interop/adapter.py "$@"\n' > /usr/local/bin/profinet-interop \
    && chmod +x /usr/local/bin/profinet-interop && mkdir -p /run/profinet-interop
ENV MIBS=""
ENTRYPOINT ["/usr/local/bin/profinet-interop"]
