#!/bin/bash
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_LIB="$SRC_DIR/purple-backup.sh"
HEARTBEAT_SRC="$SRC_DIR/purple-gentoo-heartbeat.sh"
HOST_SENSOR_SRC="$SRC_DIR/purple-host-process-sensor.sh"
HEARTBEAT_DST="/usr/local/sbin/purple-gentoo-heartbeat.sh"
HOST_SENSOR_DST="/usr/local/sbin/purple-host-process-sensor.sh"
SERVICE="/etc/systemd/system/purple-gentoo-heartbeat.service"
TIMER="/etc/systemd/system/purple-gentoo-heartbeat.timer"
HOST_SENSOR_SERVICE="/etc/systemd/system/purple-host-process-sensor.service"
HOST_SENSOR_TIMER="/etc/systemd/system/purple-host-process-sensor.timer"
HOST_POLICY="/etc/purple/host-bridge-policy.json"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    exec sudo -E "$0" "$@"
fi

backup_if_exists() {
    local file="$1"
    if [[ -e "$file" ]]; then
        if [[ -f "$BACKUP_LIB" ]]; then
            # shellcheck source=purple-backup.sh
            source "$BACKUP_LIB"
            purple_backup_file "$file" "install-purple-gentoo-heartbeat"
        else
            cp "$file" "$file.bak.$(date +%s).install.$$"
        fi
    fi
}

[[ -f "$HEARTBEAT_SRC" ]] || { echo "missing $HEARTBEAT_SRC" >&2; exit 1; }
[[ -f "$HOST_SENSOR_SRC" ]] || { echo "missing $HOST_SENSOR_SRC" >&2; exit 1; }

backup_if_exists "$HEARTBEAT_DST"
backup_if_exists "$HOST_SENSOR_DST"
backup_if_exists "$SERVICE"
backup_if_exists "$TIMER"
backup_if_exists "$HOST_SENSOR_SERVICE"
backup_if_exists "$HOST_SENSOR_TIMER"
backup_if_exists "$HOST_POLICY"

install -m 0755 "$HEARTBEAT_SRC" "$HEARTBEAT_DST"
install -m 0755 "$HOST_SENSOR_SRC" "$HOST_SENSOR_DST"
mkdir -p /etc/purple

cat > "$HOST_POLICY" << POLICY_EOF
{
  "schema": "purple-host-bridge-policy-v1",
  "mode": "owner-authorized-defensive",
  "visibility": {"owner_visible": true, "intruder_nonobvious": true, "stealth_process_hiding": false},
  "allowed_reads": ["process-summary", "listener-summary", "service-health", "bridge-health", "capsule-heartbeat"],
  "allowed_writes": ["status-files", "tamper-evident-alerts", "sealed-evidence-export"],
  "gated_actions": ["restart-purple-host-services", "refresh-owner-granted-bridge-mounts", "collect-forensic-bundle"],
  "denied_actions": ["arbitrary-shell", "credential-read", "credential-export", "firewall-mutation", "new-persistence", "lateral-movement", "process-hiding", "firmware-or-boot-modification"],
  "default_decision": "deny",
  "audit": {"append_only": true, "owner_visible": true}
}
POLICY_EOF

cat > "$SERVICE" << SERVICE_EOF
[Unit]
Description=Purple Gentoo deployment-layer heartbeat
Documentation=file:///workspaces/gentoo/purple-gentoo-heartbeat.sh
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=$HEARTBEAT_DST
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
Unit=purple-gentoo-heartbeat.service

[Install]
WantedBy=timers.target
TIMER_EOF

cat > "$HOST_SENSOR_SERVICE" << SERVICE_EOF
[Unit]
Description=Purple host process sensor
Documentation=file:///workspaces/gentoo/purple-host-process-sensor.sh
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
Unit=purple-host-process-sensor.service

[Install]
WantedBy=timers.target
TIMER_EOF

systemctl daemon-reload
systemctl enable --now purple-gentoo-heartbeat.timer
systemctl enable --now purple-host-process-sensor.timer
systemctl start purple-gentoo-heartbeat.service
systemctl start purple-host-process-sensor.service

systemctl --no-pager --plain status purple-gentoo-heartbeat.timer purple-gentoo-heartbeat.service purple-host-process-sensor.timer purple-host-process-sensor.service || true
echo "installed $HEARTBEAT_DST"
echo "installed $HOST_SENSOR_DST"
echo "status file: /run/purple-gentoo-heartbeat/status"
echo "host capsule status: /run/purple-host-capsule/status"
echo "log file: /var/log/purple-gentoo-heartbeat.log"
