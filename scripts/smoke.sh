#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
#
# Smoke test of adapter images: the command-line contract
# (scripts/check-contract.sh) for each. Images: scripts/lib.sh's image_of.
#
# Usage: scripts/smoke.sh <adapter>...
set -euo pipefail
# shellcheck source=scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require_tools
[[ $# -ge 1 ]] || { echo "usage: smoke.sh <adapter>..." >&2; exit 2; }
"$(dirname "${BASH_SOURCE[0]}")/check-contract.sh" "${TAG}" "$@" | sed 's/^/[smoke] /'
