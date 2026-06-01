#!/usr/bin/env bash
# Purple RE-deployment — self-destruct + rehydrate from GitHub
set -uo pipefail

SOPHIA_DIR="/var/lib/.sophia"
PLEIADES_REPO="https://github.com/Zheke32174/pleiades.git"
WORK_DIR="/tmp/purple-redeploy-$$"
BACKUP_DIR="/tmp/purple-backup-$$"
SELF="$0"

echo "[redeploy] Starting full re-deployment from ${PLEIADES_REPO}"

# Step 1: Backup critical state (escrow, keys, configuration)
echo "[redeploy] Backing up critical state..."
mkdir -p "$BACKUP_DIR"
if [[ -d "$SOPHIA_DIR" ]]; then
    cp -a "$SOPHIA_DIR/keys" "$BACKUP_DIR/" 2>/dev/null || true
    cp -a "$SOPHIA_DIR/escrow" "$BACKUP_DIR/" 2>/dev/null || true
    cp -a "$SOPHIA_DIR/github_drop_url" "$BACKUP_DIR/" 2>/dev/null || true
    echo "[redeploy] State backed up to $BACKUP_DIR"
fi

# Step 2: Signal self-destruct — remove all deploy artifacts
echo "[redeploy] Self-destruct phase..."
rm -rf /run/purple 2>/dev/null || true
rm -f /usr/local/bin/purple-* 2>/dev/null || true
rm -f /usr/local/sbin/install-*-omniversal.sh 2>/dev/null || true
rm -f /etc/systemd/system/purple-*.service 2>/dev/null || true
rm -f /etc/systemd/system/sophia-*.service 2>/dev/null || true
systemctl daemon-reload 2>/dev/null || true

# Step 2b: Destroy ephemeral GitHub dead drop repo
echo "[redeploy] Destroying GitHub dead drop repo..."
[[ -f /usr/local/sbin/destroy-github-drop.sh ]] && bash /usr/local/sbin/destroy-github-drop.sh

# Step 3: Clone fresh from GitHub
echo "[redeploy] Cloning $PLEIADES_REPO ..."
rm -rf "$WORK_DIR" 2>/dev/null || true
git clone --depth 1 "$PLEIADES_REPO" "$WORK_DIR" 2>/dev/null || {
    echo "[redeploy] FAILED: cannot clone repo. Restoring state and aborting."
    [[ -d "$BACKUP_DIR/keys" ]] && cp -a "$BACKUP_DIR/keys/." "$SOPHIA_DIR/keys/" 2>/dev/null || true
    exit 1
}

# Step 4: Restore critical state into fresh clone
if [[ -d "$BACKUP_DIR/keys" ]]; then
    mkdir -p "$WORK_DIR/var/lib/.sophia/keys"
    cp -a "$BACKUP_DIR/keys/." "$WORK_DIR/var/lib/.sophia/keys/" 2>/dev/null || true
fi
if [[ -d "$BACKUP_DIR/escrow" ]]; then
    mkdir -p "$WORK_DIR/var/lib/.sophia/escrow"
    cp -a "$BACKUP_DIR/escrow/." "$WORK_DIR/var/lib/.sophia/escrow/" 2>/dev/null || true
fi
if [[ -f "$BACKUP_DIR/github_drop_url" ]]; then
    mkdir -p "$WORK_DIR/var/lib/.sophia"
    cp "$BACKUP_DIR/github_drop_url" "$WORK_DIR/var/lib/.sophia/" 2>/dev/null || true
fi

# Step 5: Run installers from fresh clone
echo "[redeploy] Running installers from fresh clone..."
for installer in "$WORK_DIR"/install-scripts/*.sh; do
    [[ -f "$installer" ]] && bash "$installer" 2>/dev/null && echo "[redeploy] Ran: $installer"
done

# Step 6: Reinstall scripts to /usr/local/bin/
echo "[redeploy] Installing scripts..."
for script in "$WORK_DIR"/scripts/*.sh; do
    [[ -f "$script" ]] && cp "$script" /usr/local/bin/ 2>/dev/null || true
done
chmod +x /usr/local/bin/*.sh 2>/dev/null || true

# Step 7: Reload systemd and restart services
echo "[redeploy] Reloading systemd..."
systemctl daemon-reload 2>/dev/null || true

# Step 8: Cleanup
rm -rf "$WORK_DIR" "$BACKUP_DIR" 2>/dev/null || true
echo "[redeploy] Complete — system rehydrated from GitHub."
