#!/usr/bin/env bash
# PURGE SELF — complete self-destruct for Pleiades Team
# WARNING: This destroys the deployment. Only signal-activated.
set -uo pipefail

SIGNAL_FILE="${1:-/tmp/purge_signal}"
MAIA_DIR="/var/lib/.maia"
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
rm -rf /run/pleiades 2>/dev/null || true

# Remove binaries
for f in pleiades-forensic-scanner.sh pleiades-forensic-extensions.sh pleiades-chaos-monkey.sh Maia.sh; do
    rm -f "$PURPLE_BIN/$f" 2>/dev/null || true
    rm -f "$PURPLE_SBIN/$f" 2>/dev/null || true
done

# Remove systemd units
for unit in pleiades-*.service maia-*.service gentoo-*.service; do
    rm -f /etc/systemd/system/$unit 2>/dev/null || true
done
systemctl daemon-reload 2>/dev/null || true

# Remove maia state (preserve keys for re-deployment)
if [[ -d "$MAIA_DIR" ]]; then
    find "$MAIA_DIR" -mindepth 1 -not -path "$MAIA_DIR/keys*" -delete 2>/dev/null || true
fi

echo "[purge] Self-destruct complete. System is dormant."
echo "[purge] Re-deploy with: pleiades-redeploy.sh"
exit 0
