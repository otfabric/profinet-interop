# syntax=docker/dockerfile:1
# pnio-dcp (Codewerk GmbH, MIT), a DCP client: identify, set name and IP,
# blink, reset. Installed from PyPI at the pinned version, wheel hash
# checked.
#
# A candidate build ("make candidate-pnio-dcp CANDIDATE_VERSION=<version>
# [CANDIDATE_SHA256=<wheel sha256>]") overrides UPSTREAM_VERSION: it says
# so on stderr and skips the pinned hash; the release is checked against
# UPSTREAM_SHA256 only when that is overridden too.
FROM python:3.12.12-slim-bookworm
ARG UPSTREAM_VERSION=1.2.0
ARG UPSTREAM_SHA256=8d7d63077838c416b3dc6e58ec3790ef422e13d8bdb38be59a2da8713e3e061a
RUN --mount=type=bind,source=Dockerfile,target=/tmp/pins set -eu; \
    pinned="$(sed -nE 's/^ARG UPSTREAM_VERSION=(.+)$/\1/p' /tmp/pins | head -1)"; \
    pinned_sha256="$(sed -nE 's/^ARG UPSTREAM_SHA256=(.+)$/\1/p' /tmp/pins | head -1)"; \
    test -n "${pinned}" && test -n "${pinned_sha256}"; \
    if [ "${UPSTREAM_VERSION}" = "${pinned}" ]; then \
        printf 'pnio-dcp==%s --hash=sha256:%s\n' "$UPSTREAM_VERSION" "$UPSTREAM_SHA256" > /tmp/req.txt; \
    elif [ "${UPSTREAM_SHA256}" != "${pinned_sha256}" ]; then \
        echo "candidate build: pnio-dcp ${UPSTREAM_VERSION} instead of the pin ${pinned}, checked against the given sha256" >&2; \
        printf 'pnio-dcp==%s --hash=sha256:%s\n' "$UPSTREAM_VERSION" "$UPSTREAM_SHA256" > /tmp/req.txt; \
    else \
        echo "candidate build: pnio-dcp ${UPSTREAM_VERSION} instead of the pin ${pinned}, no hash to check" >&2; \
        printf 'pnio-dcp==%s\n' "$UPSTREAM_VERSION" > /tmp/req.txt; \
    fi
RUN if grep -q -- --hash= /tmp/req.txt; then \
        pip install --no-cache-dir --no-deps --require-hashes -r /tmp/req.txt; \
    else \
        pip install --no-cache-dir --no-deps -r /tmp/req.txt; \
    fi \
    && pip install --no-cache-dir psutil==7.1.0 importlib-metadata==8.7.0 setuptools-scm==9.2.0 \
    && mkdir -p /licenses/pnio-dcp \
    && python -c "import importlib.metadata as m; print('pnio-dcp', m.version('pnio-dcp'))"
COPY adapter.py /usr/local/lib/profinet-interop/adapter.py
RUN printf '#!/bin/sh\nexec python3 /usr/local/lib/profinet-interop/adapter.py "$@"\n' > /usr/local/bin/profinet-interop \
    && chmod +x /usr/local/bin/profinet-interop
ENTRYPOINT ["/usr/local/bin/profinet-interop"]
CMD ["print-capabilities"]
