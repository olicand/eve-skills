#!/bin/zsh
set -euo pipefail

OUTPUT_ROOT="/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/captures"
KEYLOG_FILE="${OUTPUT_ROOT}/electron_tls_keys.log"
APP_BIN="/Applications/EVE Frontier.app/Contents/MacOS/EVE Frontier"

mkdir -p "${OUTPUT_ROOT}"
touch "${KEYLOG_FILE}"

echo "Launching EVE Frontier with SSLKEYLOGFILE=${KEYLOG_FILE}"
echo "Point Wireshark TLS key log file to the same path before reproducing the auth flow."

exec env SSLKEYLOGFILE="${KEYLOG_FILE}" "${APP_BIN}" --frontier-test-servers=Utopia "$@"
