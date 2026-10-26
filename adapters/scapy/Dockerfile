# syntax=docker/dockerfile:1
# scapy (GPL-2.0-only) with its PROFINET contrib layers (pnio, pnio_dcp,
# pnio_rpc): an independent decoder of capture files. Installed from PyPI
# at the pinned version and used unmodified.
FROM python:3.12.12-slim-bookworm
ARG SCAPY_VERSION=2.6.1
RUN pip install --no-cache-dir "scapy==${SCAPY_VERSION}" \
    && python -c "import scapy; print('scapy', scapy.VERSION)"
COPY decode.py /usr/local/lib/profinet-interop/decode.py
RUN printf '#!/bin/sh\nexec python3 /usr/local/lib/profinet-interop/decode.py "$@"\n' > /usr/local/bin/profinet-interop \
    && chmod +x /usr/local/bin/profinet-interop
ENTRYPOINT ["/usr/local/bin/profinet-interop"]
CMD ["print-capabilities"]
