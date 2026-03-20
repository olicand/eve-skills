#!/bin/zsh
set -euo pipefail

OUTPUT_ROOT="/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/captures"
TSHARK_BIN="/Applications/Wireshark.app/Contents/MacOS/tshark"
INTERFACE="${1:-lo0}"
FILTER="${2:-tcp port 7890}"
TIMESTAMP="$(date +%Y%m%dT%H%M%S)"
OUTPUT_FILE="${OUTPUT_ROOT}/proxy_loopback_${TIMESTAMP}.pcapng"

mkdir -p "${OUTPUT_ROOT}"

echo "Capturing ${INTERFACE} with filter: ${FILTER}"
echo "Writing to: ${OUTPUT_FILE}"

exec "${TSHARK_BIN}" -i "${INTERFACE}" -f "${FILTER}" -w "${OUTPUT_FILE}"
