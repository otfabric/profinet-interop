# syntax=docker/dockerfile:1
# profinet-py (f0rw4rd/profinet-py, GPL-3.0-only or commercial), the
# IO-Controller reference: installed from PyPI at the pinned version and
# used unmodified, as a separate process; nothing of it is redistributed in
# this repository. A candidate build ("make candidate-profinet-py
# CANDIDATE_VERSION=<version>") overrides UPSTREAM_VERSION: it says so on
# stderr.
FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
ARG UPSTREAM_VERSION=0.6.6
RUN --mount=type=bind,source=Dockerfile,target=/tmp/pins set -eu; \
    pinned="$(sed -nE 's/^ARG UPSTREAM_VERSION=(.+)$/\1/p' /tmp/pins | head -1)"; \
    test -n "${pinned}"; \
    if [ "${UPSTREAM_VERSION}" != "${pinned}" ]; then \
        echo "candidate build: profinet-py ${UPSTREAM_VERSION} instead of the pin ${pinned}" >&2; \
    fi
RUN pip install --no-cache-dir "profinet-py==${UPSTREAM_VERSION}" \
    && python -c "import importlib.metadata as m; print('profinet-py', m.version('profinet-py'))" \
    && mkdir -p /licenses/profinet-py \
    && python -c "import importlib.metadata as m, pathlib; d=m.distribution('profinet-py'); [pathlib.Path('/licenses/profinet-py', p.name).write_text(p.read_text()) for p in d.files if 'LICENSE' in p.name.upper()]" || true
COPY adapter.py /usr/local/lib/profinet-interop/adapter.py
RUN printf '#!/bin/sh\nexec python3 /usr/local/lib/profinet-interop/adapter.py "$@"\n' > /usr/local/bin/profinet-interop \
    && chmod +x /usr/local/bin/profinet-interop
ENTRYPOINT ["/usr/local/bin/profinet-interop"]
CMD ["print-capabilities"]
