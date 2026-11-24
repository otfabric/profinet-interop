# syntax=docker/dockerfile:1
# p-net (rt-labs, GPL-3.0-only or commercial), the IO-Device reference.
#
# The public p-net branch no longer builds (it is an evaluation snapshot
# without ports). This image builds the last complete GPLv3 tree,
# ea5e5540b2be55c4dfadffda39b948632c104daa (2023-11-10), fetched by SHA from
# rtlabs-com/p-net, with its cmake-tools submodule at 5f104ff, which fetches
# osal e960068 (BSD-3-Clause). That tree predates the v1.0.2 fixes of
# CVE-2025-32396..32405: it is a lab oracle, never to be exposed.
#
# Two patches adapt it to a container network:
#  * the Ethernet speed check of Connect is skipped, because veth reports
#    10 Gbit/s, for which p-net has no MAU type (it would refuse Connect);
#  * -Werror is removed so that a current GCC builds it.
# Nothing of the p-net stack's behaviour on the wire is changed. The stack
# is built with two APIs (PNET_MAX_API=2), and one patch of the sample
# application, below, passes each slot's API to its I/O calls. The image variant
# built with --build-arg ACCEPT_IOSAR=1 also accepts the device access AR
# (ARType 0x0006), which profinet-py uses for acyclic access.
#
# The image variant built with --build-arg PROFILE_RECORDS=1 ("make
# image-pnet-profile", profinet-interop-pnet-profile) is a locally extended
# p-net, not the reference: profile-records.sh changes the stack so that the
# subslot profile indexes 0xB000-0xBFFF are application records, as the
# indexes 0x0000-0x7FFF are, and gives the sample's Digital Input/Output
# submodule a 16-octet record 0xB600. Unmodified p-net refuses a Write of
# 0xB600 (DF 80 B4 02). PF_IDX_USER_MAX and every other index stay as they
# are; a Read Implicit of a profile index is not given to the application
# (p-net has no AR for it there).
#
# UPSTREAM_SHA is the p-net commit. A candidate build ("make candidate-pnet
# CANDIDATE_SHA=<commit>") overrides it: the build says so on stderr. Later
# p-net trees are not GPL-complete (no ports), so a candidate may not build.

ARG DEBIAN=bookworm-20251020-slim@sha256:78d2f66e0fec9e5a39fb2c72ea5e052b548df75602b5215ed01a17171529f706

FROM debian:${DEBIAN} AS build
ARG UPSTREAM_SHA=ea5e5540b2be55c4dfadffda39b948632c104daa
ARG ACCEPT_IOSAR=0
ARG PROFILE_RECORDS=0
ARG LOG_LEVEL=INFO
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake git ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /src
# The pin of this file, to tell the release build from a candidate build.
RUN --mount=type=bind,source=Dockerfile,target=/tmp/pins set -eu; \
    pinned="$(sed -nE 's/^ARG UPSTREAM_SHA=(.+)$/\1/p' /tmp/pins | head -1)"; \
    test -n "${pinned}"; \
    if [ "${UPSTREAM_SHA}" != "${pinned}" ]; then \
        printf '%s' "${UPSTREAM_SHA}" | grep -qE '^[0-9a-f]{40}$' || { echo "UPSTREAM_SHA must be a full commit hash" >&2; exit 1; }; \
        echo "candidate build: p-net ${UPSTREAM_SHA} instead of the pin ${pinned} (later trees are not GPL-complete)" >&2; \
    fi
RUN git init p-net && cd p-net \
    && git remote add origin https://github.com/rtlabs-com/p-net.git \
    && git fetch --depth 1 origin "${UPSTREAM_SHA}" \
    && git checkout -q FETCH_HEAD \
    && git submodule update --init --depth 1 \
    && git -C cmake/tools log -1 --format='cmake-tools %H' \
    && git log -1 --format='p-net %H %cI'
WORKDIR /src/p-net
RUN grep -q 'return (pf_pdport_is_a_fast_port_in_use (net)) ? 0 : -1;' src/device/pf_cmdev.c \
    && sed -i 's/return (pf_pdport_is_a_fast_port_in_use (net)) ? 0 : -1;/return 0; \/* profinet-interop: veth has no MAU type *\//' src/device/pf_cmdev.c \
    && find . -type f \( -name CMakeLists.txt -o -name '*.cmake' \) -exec sed -i 's/-Werror//g' {} + \
    && if [ "${ACCEPT_IOSAR}" = 1 ]; then \
         sed -i 's/if (ar_type == PF_ART_IOCAR_SINGLE)/if ((ar_type == PF_ART_IOCAR_SINGLE) || (ar_type == PF_ART_IOSAR))/' src/device/pf_cmdev.c; \
       fi
# The sample application passes API 0 to every I/O call (its initial IOPS
# and IOCS, and its cyclic data), whatever API the controller plugged the
# module in, so an AR with a submodule of another API never gets to
# ApplicationReady (pnet_application_ready refuses: no IOPS set for that
# subslot). It now passes the API each slot was plugged in, as
# app_exp_module_ind received it. The stack is not changed; the build fails
# if the sample's code no longer matches.
RUN f=samples/pn_dev/sampleapp_common.c \
    && perl -0pi -e 's/(APP_GSDML_API|app->main_api\.api_id),(\s*)(p_)?subslot->slot_nbr,/app_slot_api[$3subslot->slot_nbr],$2$3subslot->slot_nbr,/g; s/(   ret = pnet_plug_module \(net, api, slot, module_ident\);\n)/$1   if (ret == 0)\n   {\n      app_slot_api[slot] = api; \/* profinet-interop: the API of the slot *\/\n   }\n/; s/(#include "sampleapp_common.h"\n)/$1\n\/* profinet-interop: the API each slot was plugged in. *\/\nstatic uint32_t app_slot_api[PNET_MAX_SLOTS];\n/' "$f" \
    && test "$(grep -c 'app_slot_api\[' "$f")" = 7
COPY profile-records.sh /tmp/profile-records.sh
RUN if [ "${PROFILE_RECORDS}" = 1 ]; then sh /tmp/profile-records.sh && echo "profile records: patched" > /tmp/variant; else echo "unmodified record classes" > /tmp/variant; fi
RUN cmake -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
        -DPNET_MAX_AR=2 -DPNET_MAX_API=2 -DPNET_MAX_SLOTS=8 -DPNET_MAX_SUBSLOTS=4 -DPNET_MAX_PHYSICAL_PORTS=1 \
        -DLOG_LEVEL=${LOG_LEVEL} -DPNET_LOG=ON -DPF_CPM_LOG=ON -DPF_PPM_LOG=ON -DPF_DCP_LOG=ON -DPF_RPC_LOG=ON -DPF_ALARM_LOG=ON -DPF_LLDP_LOG=ON \
    && cmake --build build --target pn_dev -j"$(nproc)" \
    && install -D build/pn_dev /out/pn_dev \
    && install -D LICENSE.md /out/licenses/p-net/LICENSE.md \
    && git log -1 --format='%H' > /out/licenses/p-net/COMMIT \
    && cp /tmp/variant /out/licenses/p-net/VARIANT \
    && git diff > /out/licenses/p-net/CHANGES.diff

FROM debian:${DEBIAN}
RUN apt-get update && apt-get install -y --no-install-recommends iproute2 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /out/pn_dev /usr/local/bin/pn_dev
COPY --from=build /out/licenses /licenses
COPY entrypoint.sh /usr/local/bin/profinet-interop
COPY set_profinet_leds set_network_parameters /usr/local/bin/
RUN chmod +x /usr/local/bin/profinet-interop /usr/local/bin/set_profinet_leds /usr/local/bin/set_network_parameters \
    && mkdir -p /var/lib/pnet /run/profinet-interop
ENV PNET_STORAGE=/var/lib/pnet
ENTRYPOINT ["/usr/local/bin/profinet-interop"]
CMD ["device"]
