# syntax=docker/dockerfile:1
# umrp (giometti/umrp, GPL-2.0), an MRP implementation (MRM, MRC, MRA)
# whose state machine runs in user space on raw sockets, with libcfm of
# microchip-ung/cfm (GPL-2.0). Built with this adapter's ifdriver_bridge.c
# (GPL-2.0): ring port states become generic Linux bridge port states, so
# no kernel MRP support (CONFIG_BRIDGE_MRP) is needed. One container is one
# ring node: a Linux bridge over two ring ports, driven by mrp_server.
#
# UPSTREAM_SHA is the umrp commit (its last tag, v4.0), CFM_SHA the cfm
# commit. A candidate build ("make candidate-umrp CANDIDATE_SHA=<commit>")
# overrides UPSTREAM_SHA: the build says so on stderr. Built locally, never
# published.
FROM debian:bookworm-20251020-slim AS build
ARG UPSTREAM_VERSION=v4.0
ARG UPSTREAM_SHA=fb193eac1a2df51fe42e19d4ea36bb0157bda09f
ARG CFM_SHA=7a50f4adcccf2d2e910816ea6d78446fea8fe7d8
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git cmake make gcc libc6-dev pkg-config \
        libnl-3-dev libnl-genl-3-dev libev-dev libmnl-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN --mount=type=bind,source=Dockerfile,target=/tmp/pins set -eu; \
    pinned="$(sed -nE 's/^ARG UPSTREAM_SHA=(.+)$/\1/p' /tmp/pins | head -1)"; \
    test -n "${pinned}"; \
    if [ "${UPSTREAM_SHA}" != "${pinned}" ]; then \
        printf '%s' "${UPSTREAM_SHA}" | grep -qE '^[0-9a-f]{40}$' || { echo "UPSTREAM_SHA must be a full commit hash" >&2; exit 1; }; \
        echo "candidate build: umrp ${UPSTREAM_VERSION} (${UPSTREAM_SHA}) instead of the pin ${pinned}" >&2; \
    fi
RUN git init cfm && cd cfm \
    && git remote add origin https://github.com/microchip-ung/cfm.git \
    && git fetch --depth 1 origin "${CFM_SHA}" && git checkout -q FETCH_HEAD \
    && cmake -B build -S . -DCMAKE_INSTALL_PREFIX=/usr/local && make -C build cfm_netlink \
    && install -D build/libcfm_netlink.a /usr/local/lib/libcfm_netlink.a \
    && install -D cfm_netlink.h /usr/local/include/cfm_netlink.h
RUN git init umrp && cd umrp \
    && git remote add origin https://github.com/giometti/umrp.git \
    && git fetch --depth 1 origin "${UPSTREAM_SHA}" && git checkout -q FETCH_HEAD
COPY ifdriver_bridge.c /src/umrp/ifdriver_bridge.c
WORKDIR /src/umrp
RUN sed -i 's/STRINGS netlink kbact/STRINGS netlink kbact bridge/' CMakeLists.txt \
    && cmake -B build -S . -DMRP_IFDRIVER=bridge && make -C build \
    && install -D build/mrp_server /out/mrp_server && install -D build/mrp /out/mrp \
    && install -D LICENSE /out/licenses/umrp/LICENSE \
    && install -D /src/cfm/LICENSE /out/licenses/cfm/LICENSE \
    && install -D ifdriver_bridge.c /out/licenses/umrp/ifdriver_bridge.c \
    && echo "${UPSTREAM_SHA}" > /out/licenses/umrp/COMMIT \
    && echo "${CFM_SHA}" > /out/licenses/cfm/COMMIT

FROM debian:bookworm-20251020-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        iproute2 nftables libnl-3-200 libnl-genl-3-200 libev4 libmnl0 mawk \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /out/mrp_server /out/mrp /usr/local/bin/
COPY --from=build /out/licenses /licenses
COPY entrypoint.sh /usr/local/bin/profinet-interop
RUN chmod +x /usr/local/bin/profinet-interop && mkdir -p /run/profinet-interop
ENTRYPOINT ["/usr/local/bin/profinet-interop"]
CMD ["node"]
