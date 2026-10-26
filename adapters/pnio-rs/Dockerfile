# syntax=docker/dockerfile:1
# pnio-rs (core-engineering/pnio-rs, MIT OR Apache-2.0), a Rust IO-Device:
# its typed_bringup example, built from tag v0.1.0. It serves a fixed
# sample device (vendor 0xFFFF, device 0x0001; inputs 16 REAL in slot 1
# and 32 BOOL in slot 2, outputs 16 REAL in slot 3 and 32 BOOL in slot 4)
# that its own GSDML (testdata/gsdml/sample-16real-32bool.xml) describes,
# and echoes the outputs into the inputs.
ARG RUST=1.90-bookworm
FROM rust:${RUST} AS build
ARG PNIO_RS_COMMIT=798500c1bf3726a1bf015c43f39c6ae2a2d55b28
WORKDIR /src
RUN git init pnio-rs && cd pnio-rs \
    && git remote add origin https://github.com/core-engineering/pnio-rs.git \
    && git fetch --depth 1 origin "${PNIO_RS_COMMIT}" && git checkout -q FETCH_HEAD
WORKDIR /src/pnio-rs
RUN cargo build --release --example typed_bringup \
    && install -D target/release/examples/typed_bringup /out/typed_bringup \
    && install -D crates/pnio/testdata/gsdml/sample-16real-32bool.xml /out/sample.xml \
    && install -D LICENSE-MIT /out/licenses/pnio-rs/LICENSE-MIT \
    && install -D LICENSE-APACHE /out/licenses/pnio-rs/LICENSE-APACHE \
    && echo "${PNIO_RS_COMMIT}" > /out/licenses/pnio-rs/COMMIT

FROM debian:bookworm-20251020-slim
RUN apt-get update && apt-get install -y --no-install-recommends iproute2 && rm -rf /var/lib/apt/lists/*
COPY --from=build /out/typed_bringup /usr/local/bin/typed_bringup
COPY --from=build /out/sample.xml /usr/share/profinet-interop/pnio-rs-sample.xml
COPY --from=build /out/licenses /licenses
COPY entrypoint.sh /usr/local/bin/profinet-interop
RUN chmod +x /usr/local/bin/profinet-interop && mkdir -p /run/profinet-interop
ENTRYPOINT ["/usr/local/bin/profinet-interop"]
CMD ["device"]
