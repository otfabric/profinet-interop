# syntax=docker/dockerfile:1
# mrp (microchip-ung/mrp, GPL-2.0): Microchip's MRP daemon (MRM, MRC, MRA)
# for the Linux bridge's MRP support, with libcfm of microchip-ung/cfm
# (GPL-2.0), with one fix (FIX_SHA, below). The kernel does the ring work (test frames,
# port states, MRP forwarding): it needs a host kernel with
# CONFIG_BRIDGE_MRP and, for a software bridge, without
# CONFIG_NET_SWITCHDEV (with switchdev built in, the kernel refuses an MRP
# instance that no switchdev driver offloads: br_mrp_switchdev_add). Neither
# Docker Desktop nor the GitHub-hosted runners qualify; the node then says
# "unsupported". One container is one ring node: a Linux bridge over
# two ring ports, driven by mrp_server.
#
# UPSTREAM_SHA is the mrp commit (master after v1.2: CMake 4 fixes),
# CFM_SHA the cfm commit. FIX_SHA is one commit on top of UPSTREAM_SHA in
# FIX_REPO, applied as a patch: an MRA that gave way to a better manager
# (now an MRC) ran the MRM state machine when the kernel reported a ring
# port's MRP_Test frames lost or back, which from CHK_RO blocked its
# secondary port for good (a hole in the ring; seen in go-profinet's
# TestMRPAuto). Proposed upstream: https://github.com/microchip-ung/mrp/pull/4;
# drop the fix when upstream has it (the patch then no longer
# applies). A candidate build ("make candidate-mrp
# CANDIDATE_SHA=<commit>") overrides UPSTREAM_SHA: the build says so on
# stderr. Built locally, never published.
FROM debian:bookworm-20251020-slim@sha256:78d2f66e0fec9e5a39fb2c72ea5e052b548df75602b5215ed01a17171529f706 AS build
ARG UPSTREAM_VERSION=v1.2
ARG UPSTREAM_SHA=177717ee893d5ccc6e31147b1b8a720c9b798b81
ARG CFM_SHA=7a50f4adcccf2d2e910816ea6d78446fea8fe7d8
ARG FIX_REPO=https://github.com/boeboe/mrp.git
ARG FIX_SHA=ee224a15af9c715fab2103c6089c371c219d7ad1
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
        echo "candidate build: mrp ${UPSTREAM_VERSION} (${UPSTREAM_SHA}) instead of the pin ${pinned}" >&2; \
    fi
RUN git init cfm && cd cfm \
    && git remote add origin https://github.com/microchip-ung/cfm.git \
    && git fetch --depth 1 origin "${CFM_SHA}" && git checkout -q FETCH_HEAD \
    && cmake -B build -S . && make -C build cfm_netlink \
    && install -D build/libcfm_netlink.a /usr/local/lib/libcfm_netlink.a \
    && install -D cfm_netlink.h /usr/local/include/cfm_netlink.h
RUN git init mrp && cd mrp \
    && git remote add origin https://github.com/microchip-ung/mrp.git \
    && git fetch --depth 1 origin "${UPSTREAM_SHA}" && git checkout -q FETCH_HEAD \
    && git remote add fix "${FIX_REPO}" && git fetch --depth 2 fix "${FIX_SHA}" \
    && git diff "${FIX_SHA}~1" "${FIX_SHA}" > /tmp/fix.patch && git apply /tmp/fix.patch \
    && mkdir -p /out/licenses/mrp && cp /tmp/fix.patch /out/licenses/mrp/fix.patch
WORKDIR /src/mrp
RUN cmake -B build -S . && make -C build \
    && install -D build/mrp_server /out/mrp_server && install -D build/mrp /out/mrp \
    && install -D LICENSE /out/licenses/mrp/LICENSE \
    && install -D /src/cfm/LICENSE /out/licenses/cfm/LICENSE \
    && echo "${UPSTREAM_SHA}" > /out/licenses/mrp/COMMIT \
    && echo "${FIX_SHA}" > /out/licenses/mrp/FIX_COMMIT \
    && echo "${CFM_SHA}" > /out/licenses/cfm/COMMIT

FROM debian:bookworm-20251020-slim@sha256:78d2f66e0fec9e5a39fb2c72ea5e052b548df75602b5215ed01a17171529f706
RUN apt-get update && apt-get install -y --no-install-recommends \
        iproute2 nftables libnl-3-200 libnl-genl-3-200 libev4 libmnl0 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /out/mrp_server /out/mrp /usr/local/bin/
COPY --from=build /out/licenses /licenses
COPY entrypoint.sh /usr/local/bin/profinet-interop
RUN chmod +x /usr/local/bin/profinet-interop && mkdir -p /run/profinet-interop
ENTRYPOINT ["/usr/local/bin/profinet-interop"]
CMD ["node"]
