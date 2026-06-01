#!/usr/bin/env bash
# PURGE SELF — complete self-destruct for Purple Team
# WARNING: This destroys the deployment. Only signal-activated.
set -uo pipefail

SIGNAL_FILE="${1:-/tmp/purge_signal}"
SOPHIA_DIR="/var/lib/.sophia"
PURPLE_BIN="/usr/local/bin"
PURPLE_SBIN="/usr/local/sbin"

# Require a signal file with "AUTHORIZED_PURGE" to prevent accidental runs
if [[ ! -f "$SIGNAL_FILE" ]] || ! grep -q "AUTHORIZED_PURGE" "$SIGNAL_FILE" 2>/dev/null; then
    echo "[purge] ERROR: No valid purge signal at $SIGNAL_FILE"
    echo "[purge] To authorize: echo 'AUTHORIZED_PURGE' > $SIGNAL_FILE"
    exit 1
fi

echo "[purge] PURGE AUTHORIZED — destroying Purple deployment..."

# Remove run state
rm -rf /run/purple 2>/dev/null || true

# Remove binaries
for f in purple-forensic-scanner.sh purple-forensic-extensions.sh purple-chaos-monkey.sh SofiaX.sh; do
    rm -f "$PURPLE_BIN/$f" 2>/dev/null || true
    rm -f "$PURPLE_SBIN/$f" 2>/dev/null || true
done

# Remove systemd units
for unit in purple-*.service sophia-*.service gentoo-*.service; do
    rm -f /etc/systemd/system/$unit 2>/dev/null || true
done
systemctl daemon-reload 2>/dev/null || true

# Remove sophia state (preserve keys for re-deployment)
if [[ -d "$SOPHIA_DIR" ]]; then
    find "$SOPHIA_DIR" -mindepth 1 -not -path "$SOPHIA_DIR/keys*" -delete 2>/dev/null || true
fi

echo "[purge] Self-destruct complete. System is dormant."
echo "[purge] Re-deploy with: purple-redeploy.sh"
exit 0
