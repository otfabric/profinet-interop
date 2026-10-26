# syntax=docker/dockerfile:1
# pnio-dcp (Codewerk GmbH, MIT), a DCP client: identify, set name and IP,
# blink, reset. Installed from PyPI at the pinned version, wheel hash
# checked.
FROM python:3.12.12-slim-bookworm
ARG PNIO_DCP_VERSION=1.2.0
ARG PNIO_DCP_SHA256=8d7d63077838c416b3dc6e58ec3790ef422e13d8bdb38be59a2da8713e3e061a
RUN printf 'pnio-dcp==%s --hash=sha256:%s\n' "$PNIO_DCP_VERSION" "$PNIO_DCP_SHA256" > /tmp/req.txt \
    && pip install --no-cache-dir --no-deps --require-hashes -r /tmp/req.txt \
    && pip install --no-cache-dir psutil==7.1.0 importlib-metadata==8.7.0 setuptools-scm==9.2.0 \
    && mkdir -p /licenses/pnio-dcp \
    && python -c "import importlib.metadata as m; print('pnio-dcp', m.version('pnio-dcp'))"
COPY adapter.py /usr/local/lib/profinet-interop/adapter.py
RUN printf '#!/bin/sh\nexec python3 /usr/local/lib/profinet-interop/adapter.py "$@"\n' > /usr/local/bin/profinet-interop \
    && chmod +x /usr/local/bin/profinet-interop
ENTRYPOINT ["/usr/local/bin/profinet-interop"]
CMD ["print-capabilities"]
