# syntax=docker/dockerfile:1
# pnio-rs (core-engineering/pnio-rs, MIT OR Apache-2.0), a Rust IO-Device:
# its typed_bringup example, built from tag v0.1.0. It serves a fixed
# sample device (vendor 0xFFFF, device 0x0001; inputs 16 REAL in slot 1
# and 32 BOOL in slot 2, outputs 16 REAL in slot 3 and 32 BOOL in slot 4)
# that its own GSDML (testdata/gsdml/sample-16real-32bool.xml) describes,
# and echoes the outputs into the inputs.
#
# UPSTREAM_VERSION is the release tag, UPSTREAM_SHA its commit (what is
# fetched). A candidate build ("make candidate-pnio-rs CANDIDATE_VERSION=<tag>
# CANDIDATE_SHA=<commit>") overrides them: the build says so on stderr.
ARG RUST=1.90-bookworm@sha256:3914072ca0c3b8aad871db9169a651ccfce30cf58303e5d6f2db16d1d8a7e58f
FROM rust:${RUST} AS build
ARG UPSTREAM_VERSION=v0.1.0
ARG UPSTREAM_SHA=798500c1bf3726a1bf015c43f39c6ae2a2d55b28
WORKDIR /src
# The pin of this file, to tell the release build from a candidate build.
RUN --mount=type=bind,source=Dockerfile,target=/tmp/pins set -eu; \
    pinned="$(sed -nE 's/^ARG UPSTREAM_SHA=(.+)$/\1/p' /tmp/pins | head -1)"; \
    test -n "${pinned}"; \
    if [ "${UPSTREAM_SHA}" != "${pinned}" ]; then \
        printf '%s' "${UPSTREAM_SHA}" | grep -qE '^[0-9a-f]{40}$' || { echo "UPSTREAM_SHA must be a full commit hash" >&2; exit 1; }; \
        echo "candidate build: pnio-rs ${UPSTREAM_VERSION} (${UPSTREAM_SHA}) instead of the pin ${pinned}" >&2; \
    fi
RUN git init pnio-rs && cd pnio-rs \
    && git remote add origin https://github.com/core-engineering/pnio-rs.git \
    && git fetch --depth 1 origin "${UPSTREAM_SHA}" && git checkout -q FETCH_HEAD
WORKDIR /src/pnio-rs
RUN cargo build --release --example typed_bringup \
    && install -D target/release/examples/typed_bringup /out/typed_bringup \
    && install -D crates/pnio/testdata/gsdml/sample-16real-32bool.xml /out/sample.xml \
    && install -D LICENSE-MIT /out/licenses/pnio-rs/LICENSE-MIT \
    && install -D LICENSE-APACHE /out/licenses/pnio-rs/LICENSE-APACHE \
    && echo "${UPSTREAM_SHA}" > /out/licenses/pnio-rs/COMMIT

FROM debian:bookworm-20251020-slim@sha256:78d2f66e0fec9e5a39fb2c72ea5e052b548df75602b5215ed01a17171529f706
RUN apt-get update && apt-get install -y --no-install-recommends iproute2 && rm -rf /var/lib/apt/lists/*
COPY --from=build /out/typed_bringup /usr/local/bin/typed_bringup
COPY --from=build /out/sample.xml /usr/share/profinet-interop/pnio-rs-sample.xml
COPY --from=build /out/licenses /licenses
COPY entrypoint.sh /usr/local/bin/profinet-interop
RUN chmod +x /usr/local/bin/profinet-interop && mkdir -p /run/profinet-interop
ENTRYPOINT ["/usr/local/bin/profinet-interop"]
CMD ["device"]
