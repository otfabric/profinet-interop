# syntax=docker/dockerfile:1
# scapy (GPL-2.0-only) with its PROFINET contrib layers (pnio, pnio_dcp,
# pnio_rpc): an independent decoder of capture files. Installed from PyPI
# at the pinned version and used unmodified. A candidate build ("make
# candidate-scapy CANDIDATE_VERSION=<version>") overrides UPSTREAM_VERSION:
# it says so on stderr.
FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
ARG UPSTREAM_VERSION=2.6.1
RUN --mount=type=bind,source=Dockerfile,target=/tmp/pins set -eu; \
    pinned="$(sed -nE 's/^ARG UPSTREAM_VERSION=(.+)$/\1/p' /tmp/pins | head -1)"; \
    test -n "${pinned}"; \
    if [ "${UPSTREAM_VERSION}" != "${pinned}" ]; then \
        echo "candidate build: scapy ${UPSTREAM_VERSION} instead of the pin ${pinned}" >&2; \
    fi
RUN pip install --no-cache-dir "scapy==${UPSTREAM_VERSION}" \
    && python -c "import scapy; print('scapy', scapy.VERSION)"
COPY decode.py /usr/local/lib/profinet-interop/decode.py
RUN printf '#!/bin/sh\nexec python3 /usr/local/lib/profinet-interop/decode.py "$@"\n' > /usr/local/bin/profinet-interop \
    && chmod +x /usr/local/bin/profinet-interop
ENTRYPOINT ["/usr/local/bin/profinet-interop"]
CMD ["print-capabilities"]
