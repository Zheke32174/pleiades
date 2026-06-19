#!/bin/bash
source "${PLEIADES_TERMUX_LIB:-}" 2>/dev/null || true
set -euo pipefail

# Termux: systemd service installer (not applicable)
[[ "${PLEIADES_ENV:-}" == "termux" ]] && echo "[install-heartbeat] Termux: no systemd, skipping" && exit 0

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_LIB="$SRC_DIR/pleiades-backup.sh"
HEARTBEAT_SRC="$SRC_DIR/pleiades-gentoo-heartbeat.sh"
HOST_SENSOR_SRC="$SRC_DIR/pleiades-host-process-sensor.sh"
BRIDGE_SCRIPT_SRC="$SRC_DIR/pleiades-ensure-host-bridges.sh"
HEARTBEAT_DST="/usr/local/sbin/pleiades-gentoo-heartbeat.sh"
HOST_SENSOR_DST="/usr/local/sbin/pleiades-host-process-sensor.sh"
BRIDGE_SCRIPT_DST="/usr/local/sbin/pleiades-ensure-host-bridges.sh"
SERVICE="/etc/systemd/system/pleiades-gentoo-heartbeat.service"
TIMER="/etc/systemd/system/pleiades-gentoo-heartbeat.timer"
HOST_SENSOR_SERVICE="/etc/systemd/system/pleiades-host-process-sensor.service"
HOST_SENSOR_TIMER="/etc/systemd/system/pleiades-host-process-sensor.timer"
HOST_POLICY="/etc/pleiades/host-bridge-policy.json"
BRIDGE_SERVICE="/etc/systemd/system/pleiades-host-bridges.service"
BRIDGE_REFRESH_SERVICE="/etc/systemd/system/pleiades-host-bridges-refresh.service"
BRIDGE_PATH="/etc/systemd/system/pleiades-host-bridges.path"
WSL_REMOUNT_SERVICE="/etc/systemd/system/wsl-remount-drives.service"
PROC_MOUNT="/etc/systemd/system/workspaces-gentoo-root.x86_64-host-proc.mount"
SYS_MOUNT="/etc/systemd/system/workspaces-gentoo-root.x86_64-host-sys.mount"
ROOT="${PURPLE_GENTOO_ROOT:-${PLEIADES_ROOT:-${HOME}/pleiades}/rootfs}"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    exec sudo -E "$0" "$@"
fi

backup_if_exists() {
    local file="$1"
    if [[ -e "$file" ]]; then
        if [[ -f "$BACKUP_LIB" ]]; then
            # shellcheck source=pleiades-backup.sh
            source "$BACKUP_LIB"
            pleiades_backup_file "$file" "install-pleiades-gentoo-heartbeat"
        else
            cp "$file" "$file.bak.$(date +%s).install.$$"
        fi
    fi
}

[[ -f "$HEARTBEAT_SRC" ]] || { echo "missing $HEARTBEAT_SRC" >&2; exit 1; }
[[ -f "$HOST_SENSOR_SRC" ]] || { echo "missing $HOST_SENSOR_SRC" >&2; exit 1; }

backup_if_exists "$HEARTBEAT_DST"
backup_if_exists "$HOST_SENSOR_DST"
backup_if_exists "$BRIDGE_SCRIPT_DST"
backup_if_exists "$SERVICE"
backup_if_exists "$TIMER"
backup_if_exists "$HOST_SENSOR_SERVICE"
backup_if_exists "$HOST_SENSOR_TIMER"
backup_if_exists "$HOST_POLICY"
backup_if_exists "$BRIDGE_SERVICE"
backup_if_exists "$BRIDGE_REFRESH_SERVICE"
backup_if_exists "$BRIDGE_PATH"
backup_if_exists "$PROC_MOUNT"
backup_if_exists "$SYS_MOUNT"

[[ -f "$BRIDGE_SCRIPT_SRC" ]] || { echo "missing $BRIDGE_SCRIPT_SRC" >&2; exit 1; }

install -m 0755 "$HEARTBEAT_SRC" "$HEARTBEAT_DST"
install -m 0755 "$HOST_SENSOR_SRC" "$HOST_SENSOR_DST"
install -m 0755 "$BRIDGE_SCRIPT_SRC" "$BRIDGE_SCRIPT_DST"
mkdir -p /etc/pleiades

cat > "$HOST_POLICY" << POLICY_EOF
{
  "schema": "pleiades-host-bridge-policy-v1",
  "mode": "owner-authorized-defensive",
  "visibility": {"owner_visible": true, "intruder_nonobvious": true, "stealth_process_hiding": false},
  "allowed_reads": ["process-summary", "listener-summary", "service-health", "bridge-health", "capsule-heartbeat"],
  "allowed_writes": ["status-files", "tamper-evident-alerts", "sealed-evidence-export"],
  "gated_actions": ["restart-pleiades-host-services", "refresh-owner-granted-bridge-mounts", "collect-forensic-bundle"],
  "denied_actions": ["arbitrary-shell", "credential-read", "credential-export", "firewall-mutation", "new-persistence", "lateral-movement", "process-hiding", "firmware-or-boot-modification"],
  "default_decision": "deny",
  "audit": {"append_only": true, "owner_visible": true}
}
POLICY_EOF

cat > "$SERVICE" << SERVICE_EOF
[Unit]
Description=Purple Gentoo deployment-layer heartbeat
Documentation=file://${ROOT}/../pleiades-gentoo-heartbeat.sh
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=$HEARTBEAT_DST
KillMode=process
Nice=5
IOSchedulingClass=best-effort
IOSchedulingPriority=6
TimeoutStopSec=130
SERVICE_EOF

cat > "$TIMER" << TIMER_EOF
[Unit]
Description=Run Purple Gentoo deployment-layer heartbeat

[Timer]
OnBootSec=30s
OnUnitActiveSec=60s
AccuracySec=10s
Persistent=true
Unit=pleiades-gentoo-heartbeat.service

[Install]
WantedBy=timers.target
TIMER_EOF

cat > "$HOST_SENSOR_SERVICE" << SERVICE_EOF
[Unit]
Description=Purple host process sensor
Documentation=file://${ROOT}/../pleiades-host-process-sensor.sh
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=$HOST_SENSOR_DST
Nice=5
IOSchedulingClass=best-effort
IOSchedulingPriority=6
SERVICE_EOF

cat > "$HOST_SENSOR_TIMER" << TIMER_EOF
[Unit]
Description=Run Purple host process sensor

[Timer]
OnBootSec=45s
OnUnitActiveSec=30s
AccuracySec=5s
Persistent=true
Unit=pleiades-host-process-sensor.service

[Install]
WantedBy=timers.target
TIMER_EOF

# ── Task #1: Host bridge mount persistence units ──────────────────────────────

cat > "$PROC_MOUNT" << MOUNT_EOF
[Unit]
Description=Purple Host Bridge — /proc (read-only)
Documentation=file://${ROOT}/../pleiades-ensure-host-bridges.sh
DefaultDependencies=no
Before=pleiades-host-bridges.service pleiades-gentoo-heartbeat.service local-fs.target

[Mount]
What=proc
Where=$ROOT/host/proc
Type=proc
Options=ro,nosuid,nodev,noexec,noatime

[Install]
WantedBy=local-fs.target
MOUNT_EOF

cat > "$SYS_MOUNT" << MOUNT_EOF
[Unit]
Description=Purple Host Bridge — /sys (read-only)
Documentation=file://${ROOT}/../pleiades-ensure-host-bridges.sh
DefaultDependencies=no
Before=pleiades-host-bridges.service pleiades-gentoo-heartbeat.service local-fs.target

[Mount]
What=sysfs
Where=$ROOT/host/sys
Type=sysfs
Options=ro,nosuid,nodev,noexec,noatime

[Install]
WantedBy=local-fs.target
MOUNT_EOF

cat > "$BRIDGE_SERVICE" << SERVICE_EOF
[Unit]
Description=Purple Gentoo nspawn host bridge mounts
Documentation=file://${ROOT}/../pleiades-ensure-host-bridges.sh
DefaultDependencies=no
After=local-fs.target wsl-remount-drives.service
After=workspaces-gentoo-root.x86_64-host-proc.mount workspaces-gentoo-root.x86_64-host-sys.mount
Before=pleiades-gentoo-heartbeat.service
Wants=workspaces-gentoo-root.x86_64-host-proc.mount workspaces-gentoo-root.x86_64-host-sys.mount

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=$BRIDGE_SCRIPT_DST
ExecReload=$BRIDGE_SCRIPT_DST
TimeoutStartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=local-fs.target
SERVICE_EOF

cat > "$BRIDGE_REFRESH_SERVICE" << SERVICE_EOF
[Unit]
Description=Purple host bridge refresh (triggered by container status change)
DefaultDependencies=no
After=pleiades-host-bridges.service

[Service]
Type=oneshot
ExecStart=$BRIDGE_SCRIPT_DST
StandardOutput=journal
StandardError=journal
SERVICE_EOF

cat > "$BRIDGE_PATH" << PATH_EOF
[Unit]
Description=Watch for Gentoo container restart to refresh host bridges
After=pleiades-host-bridges.service

[Path]
PathChanged=/run/pleiades-gentoo-heartbeat/status
Unit=pleiades-host-bridges-refresh.service

[Install]
WantedBy=multi-user.target
PATH_EOF

# Ensure WSL remount-drives service script exists
if [[ ! -x /usr/local/sbin/wsl-remount-drives.sh ]]; then
    cat > /usr/local/sbin/wsl-remount-drives.sh << 'SCRIPT_EOF'
#!/bin/bash
for letter in c d; do
    mnt="/mnt/$letter"
    if mountpoint -q "$mnt" 2>/dev/null && ! ls "$mnt" > /dev/null 2>&1; then
        umount -l "$mnt" 2>/dev/null || true
        mount -t drvfs "${letter^^}:" "$mnt" 2>/dev/null && \
            logger "wsl-remount: remounted stale $mnt"
    fi
done
for letter in c d; do
    src="/mnt/$letter"
    dst="$ROOT/host/mnt/$letter"
    [ -d "$dst" ] && mountpoint -q "$src" && \
        ! ls "$dst" > /dev/null 2>&1 && \
        mount --bind "$src" "$dst" 2>/dev/null && \
        logger "wsl-remount: rebound $dst"
done
SCRIPT_EOF
    chmod 0755 /usr/local/sbin/wsl-remount-drives.sh
fi

# Ensure wsl-remount-drives.service exists
if [[ ! -f "$WSL_REMOUNT_SERVICE" ]]; then
    cat > "$WSL_REMOUNT_SERVICE" << SERVICE_EOF
[Unit]
Description=Remount stale WSL DrvFS Windows drives
DefaultDependencies=no
Before=network-pre.target
After=local-fs-pre.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/wsl-remount-drives.sh

[Install]
WantedBy=local-fs.target
SERVICE_EOF
fi

# ── Enable and start everything ───────────────────────────────────────────────
systemctl daemon-reload
systemctl enable workspaces-gentoo-root.x86_64-host-proc.mount
systemctl enable workspaces-gentoo-root.x86_64-host-sys.mount
systemctl enable --now wsl-remount-drives.service
systemctl enable --now pleiades-host-bridges.service
systemctl enable --now pleiades-host-bridges.path
systemctl enable --now pleiades-gentoo-heartbeat.timer
systemctl enable --now pleiades-host-process-sensor.timer
systemctl start pleiades-gentoo-heartbeat.service
systemctl start pleiades-host-process-sensor.service

systemctl --no-pager --plain status \
    pleiades-host-bridges.service \
    pleiades-gentoo-heartbeat.timer pleiades-gentoo-heartbeat.service \
    pleiades-host-process-sensor.timer pleiades-host-process-sensor.service \
    || true
echo "installed $HEARTBEAT_DST"
echo "installed $HOST_SENSOR_DST"
echo "installed $BRIDGE_SCRIPT_DST"
echo "status file: /run/pleiades-gentoo-heartbeat/status"
echo "host capsule status: /run/pleiades-host-capsule/status"
echo "log file: /var/log/pleiades-gentoo-heartbeat.log"
echo "bridge units: pleiades-host-bridges.service / .path / proc.mount / sys.mount"
