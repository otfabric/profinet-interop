# syntax=docker/dockerfile:1
# tshark (Wireshark, GPL-2.0-or-later) from Debian: a passive oracle. Its
# PROFINET dissectors (PN-DCP, PN-RT, PN-IO, PNIO-CM, LLDP) decode a
# capture; the adapter reports malformed frames and expert warnings.
FROM debian:bookworm-20251020-slim
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tshark jq \
    && rm -rf /var/lib/apt/lists/* && tshark --version | head -1
COPY check.sh /usr/local/bin/profinet-interop
RUN chmod +x /usr/local/bin/profinet-interop
ENTRYPOINT ["/usr/local/bin/profinet-interop"]
CMD ["print-capabilities"]
