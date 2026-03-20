#!/bin/zsh
set -euo pipefail

OUTPUT_ROOT="/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/captures"
KEYLOG_FILE="${OUTPUT_ROOT}/chrome_tls_keys.log"
APP_NAME="Google Chrome"

mkdir -p "${OUTPUT_ROOT}"
touch "${KEYLOG_FILE}"

echo "Setting launchd SSLKEYLOGFILE=${KEYLOG_FILE}"
launchctl setenv SSLKEYLOGFILE "${KEYLOG_FILE}"

echo "Launching ${APP_NAME} with TLS key logging enabled"
echo "Wireshark TLS key log file: ${KEYLOG_FILE}"
echo "Quit all running ${APP_NAME} windows first so the new process inherits SSLKEYLOGFILE."
echo "After you finish capturing, clear the env with:"
echo "  launchctl unsetenv SSLKEYLOGFILE"

open -a "${APP_NAME}" --new --args "$@"
