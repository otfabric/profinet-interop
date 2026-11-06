#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
#
# Cross-stack self-test of the given adapters on Layer 2 (scripts/interop.py,
# tests/cases.tsv). Images: scripts/lib.sh's image_of. Writes
# ${REPORT_DIR:-reports}/results.json.
#
# Usage: scripts/interop.sh <adapter> <adapter>...
set -euo pipefail
# shellcheck source=scripts/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
require_tools
[[ $# -ge 1 ]] || { echo "usage: interop.sh <adapter>..." >&2; exit 2; }
export TAG
exec python3 "$(dirname "${BASH_SOURCE[0]}")/interop.py" "$@"
