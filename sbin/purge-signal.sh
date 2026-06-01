#!/usr/bin/env bash
# Purge signal from GitHub dead drop
# If the signed message from the GitHub drop matches "PURGE|AUTHORIZED_PURGE",
# create the signal file to authorize self-destruct.
set -uo pipefail

GITHUB_URL_FILE="/var/lib/.sophia/github_drop_url"
SIGNAL_FILE="/tmp/purge_signal"

if [[ ! -f "$GITHUB_URL_FILE" ]]; then
    exit 0
fi

URL=$(cat "$GITHUB_URL_FILE")
MESSAGE=$(curl -s --max-time 10 "$URL" | sophia_crypto verify-drop /dev/stdin 2>/dev/null || echo "")

if echo "$MESSAGE" | grep -q "PURGE|AUTHORIZED_PURGE" 2>/dev/null; then
    echo "AUTHORIZED_PURGE" > "$SIGNAL_FILE"
    echo "[purge-signal] Purge signal received from GitHub dead drop."
    exit 0
fi
echo "[purge-signal] No purge signal detected."
exit 1
