#!/bin/bash
# install-boot-persistence.sh — Machine Runtime Monitor boot persistence installer
#
# Detects WSL / bare metal / VPS and installs the appropriate persistence mechanism
# so the Pleiades nspawn container starts automatically at OS boot.
#
# Hardening:
#   - Restart=always + StartLimitIntervalSec=0 (survives crashes)
#   - chattr +i on binary and unit file (attacker can't delete without knowing trick)
#   - Owner escape hatch: maia_crypto issue-stop → signed STOP token
#   - Host footprint: one wrapper + one service unit, nothing else on the host
#
# Usage: bash install-boot-persistence.sh [--dry-run] [--uninstall]

set -euo pipefail

# ------------------------------------------------------------
# Config
# ------------------------------------------------------------
CONTAINER_ROOT="/workspaces/gentoo/root.x86_64"
CONTAINER_NAME="pleiades"
HOST_WRAPPER="/usr/local/sbin/machine-runtime-monitor"
SERVICE_NAME="machine-runtime-monitor"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
WSL_CONF="/etc/wsl.conf"
MAIA_DIR="/var/lib/.maia"
LOG_TAG="pleiades-boot"

DRY_RUN=false
UNINSTALL=false
for arg in "$@"; do
    [[ "$arg" == "--dry-run" ]]  && DRY_RUN=true
    [[ "$arg" == "--uninstall" ]] && UNINSTALL=true
done

log()  { logger -t "$LOG_TAG" "$*" 2>/dev/null; echo "[$LOG_TAG] $*"; }
run()  { if $DRY_RUN; then echo "[DRY-RUN] $*"; else "$@"; fi; }
die()  { echo "ERROR: $*" >&2; exit 1; }

[[ "${EUID:-$(id -u)}" -ne 0 ]] && die "Must run as root"

# ------------------------------------------------------------
# Environment detection
# ------------------------------------------------------------
detect_env() {
    if grep -qi microsoft /proc/version 2>/dev/null; then
        echo "wsl"
    elif [[ -d /sys/firmware/efi ]] && ! systemd-detect-virt --container -q 2>/dev/null && ! systemd-detect-virt --vm -q 2>/dev/null; then
        echo "bare_metal"
    elif dmidecode -s system-manufacturer 2>/dev/null | grep -qiE "kvm|xen|vmware|virtualbox|microsoft"; then
        echo "vps"
    else
        echo "bare_metal"
    fi
}

ENV=$(detect_env)
log "Detected environment: $ENV"

# ------------------------------------------------------------
# Uninstall path
# ------------------------------------------------------------
if $UNINSTALL; then
    log "Uninstalling boot persistence..."
    if [[ "$ENV" == "wsl" ]]; then
        if [[ -f "$WSL_CONF" ]]; then
            sed -i '/^\[boot\]/,/^command=/d' "$WSL_CONF" 2>/dev/null || true
            log "Removed [boot] command from $WSL_CONF"
        fi
    else
        if systemctl is-active "$SERVICE_NAME" &>/dev/null; then
            chattr -i "$SERVICE_FILE" "$HOST_WRAPPER" 2>/dev/null || true
            systemctl stop "$SERVICE_NAME" || true
            systemctl disable "$SERVICE_NAME" || true
        fi
        rm -f "$SERVICE_FILE" "$HOST_WRAPPER"
        systemctl daemon-reload 2>/dev/null || true
        log "Removed $SERVICE_NAME systemd service and wrapper"
    fi
    log "Uninstall complete."
    exit 0
fi

# ------------------------------------------------------------
# Write host wrapper script
# ------------------------------------------------------------
write_wrapper() {
    run mkdir -p "$(dirname "$HOST_WRAPPER")"
    if ! $DRY_RUN; then
        cat > "$HOST_WRAPPER" << 'WRAPPER'
#!/bin/bash
# machine-runtime-monitor — host wrapper that starts the Pleiades nspawn container.
# Managed by machine-runtime-monitor.service. Do not delete.

CONTAINER_ROOT="/workspaces/gentoo/root.x86_64"
STOP_TOKEN="/var/lib/.maia/owner_stop"
LOG_TAG="machine-runtime-monitor"

# Owner escape hatch: if a valid signed STOP token exists, do not start
if [[ -f "$STOP_TOKEN" ]] && command -v maia_crypto &>/dev/null; then
    if maia_crypto verify "$STOP_TOKEN" 2>/dev/null; then
        logger -t "$LOG_TAG" "Signed STOP token found — staying dormant per owner instruction"
        exit 0
    fi
fi

# Start nspawn container
exec systemd-nspawn \
    --directory="$CONTAINER_ROOT" \
    --machine=pleiades \
    --boot \
    --bind=/run/pleiades \
    --bind=/var/lib/.maia \
    --bind-ro=/etc/machine-id \
    --bind-ro=/etc/hostname \
    --network-veth \
    --settings=trusted \
    "$@"
WRAPPER
        chmod 700 "$HOST_WRAPPER"
    fi
    log "Host wrapper written: $HOST_WRAPPER"
}

# ------------------------------------------------------------
# WSL persistence via /etc/wsl.conf [boot]
# ------------------------------------------------------------
install_wsl() {
    log "Installing WSL boot persistence..."
    write_wrapper

    # Ensure [boot] section in wsl.conf
    local boot_cmd="$HOST_WRAPPER"

    if ! $DRY_RUN; then
        # Remove any existing [boot] command line
        if [[ -f "$WSL_CONF" ]]; then
            # Check if already installed
            if grep -q "machine-runtime-monitor\|pleiades" "$WSL_CONF" 2>/dev/null; then
                log "WSL boot entry already present in $WSL_CONF"
                return
            fi
            # Append [boot] section
            if grep -q '^\[boot\]' "$WSL_CONF"; then
                sed -i "/^\[boot\]/a command=${boot_cmd}" "$WSL_CONF"
            else
                printf '\n[boot]\ncommand=%s\n' "$boot_cmd" >> "$WSL_CONF"
            fi
        else
            cat > "$WSL_CONF" << WSLCONF
[boot]
command=${boot_cmd}

[wsl2]
memory=4GB
processors=2
WSLCONF
        fi
    fi

    log "WSL boot persistence installed: $WSL_CONF → command=$boot_cmd"
    log "NOTE: Takes effect on next 'wsl --shutdown' + WSL restart"

    # Windows Task Scheduler fallback (belt-and-suspenders for WSL auto-start)
    if command -v powershell.exe &>/dev/null; then
        if ! $DRY_RUN; then
            powershell.exe -NoProfile -Command "
                \$action  = New-ScheduledTaskAction -Execute 'wsl.exe' -Argument '-u root -- bash -c \"${boot_cmd} &\"'
                \$trigger = New-ScheduledTaskTrigger -AtLogOn
                \$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
                \$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
                Register-ScheduledTask -TaskName 'PleiadesAutoStart' -Action \$action \`
                    -Trigger \$trigger -Settings \$settings -Principal \$principal \`
                    -Description 'Pleiades purple team container auto-start' \`
                    -Force | Out-Null
                Write-Output 'Task Scheduler entry registered: PleiadesAutoStart'
            " 2>/dev/null && log "Windows Task Scheduler: PleiadesAutoStart registered" || \
                log "WARN: Task Scheduler registration failed (non-fatal)"
        fi
    fi
}

# ------------------------------------------------------------
# Bare metal / VPS persistence via systemd service
# ------------------------------------------------------------
install_systemd() {
    log "Installing systemd boot persistence..."
    write_wrapper

    if ! $DRY_RUN; then
        cat > "$SERVICE_FILE" << SERVICE
[Unit]
Description=Machine Runtime Monitor
Documentation=https://github.com/Zheke32174/pleiades
After=network.target local-fs.target
Wants=network.target

[Service]
Type=simple
ExecStart=${HOST_WRAPPER}
Restart=always
RestartSec=5
StartLimitIntervalSec=0
StandardOutput=journal
StandardError=journal
SyslogIdentifier=machine-runtime-monitor

# Resource limits
LimitNOFILE=1048576
MemoryMax=4G
CPUQuota=400%

[Install]
WantedBy=multi-user.target
SERVICE

        systemctl daemon-reload
        systemctl enable "$SERVICE_NAME"
        systemctl start "$SERVICE_NAME" || log "WARN: service start failed (container may not be ready)"

        # Harden: make binary and unit immutable to root (attacker-resistant)
        # Owner can undo with: chattr -i <file>
        if command -v chattr &>/dev/null; then
            chattr +i "$HOST_WRAPPER" "$SERVICE_FILE" 2>/dev/null && \
                log "chattr +i applied to wrapper and service file (attacker-resistant)" || \
                log "WARN: chattr +i failed (non-fatal)"
        fi
    fi

    log "systemd service installed: $SERVICE_FILE"
    log "Status: $(systemctl is-active "$SERVICE_NAME" 2>/dev/null || echo 'unknown')"
}

# ------------------------------------------------------------
# Owner escape hatch setup
# ------------------------------------------------------------
setup_escape_hatch() {
    if command -v maia_crypto &>/dev/null; then
        run mkdir -p "$MAIA_DIR/keys"
        log "Owner escape hatch: run 'maia_crypto issue-stop' to create signed STOP token"
        log "STOP token path: $MAIA_DIR/owner_stop"
        log "To resume: rm $MAIA_DIR/owner_stop && systemctl restart $SERVICE_NAME"
    else
        log "WARN: maia_crypto not found — escape hatch requires it"
        log "      Install with: bash $CONTAINER_ROOT/scripts/Maia.sh --install-crypto-only"
    fi
}

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
log "Installing Pleiades boot persistence (env=$ENV, dry_run=$DRY_RUN)"
run mkdir -p /run/pleiades "$MAIA_DIR"

case "$ENV" in
    wsl)        install_wsl ;;
    bare_metal) install_systemd ;;
    vps)        install_systemd ;;
    *)          install_systemd ;;
esac

setup_escape_hatch

log ""
log "Boot persistence installed successfully."
log "Container: $CONTAINER_ROOT"
log "Wrapper:   $HOST_WRAPPER"
if [[ "$ENV" == "wsl" ]]; then
    log "Activation: wsl --shutdown && restart WSL"
else
    log "Service:    $(systemctl is-enabled "$SERVICE_NAME" 2>/dev/null || echo 'unknown')"
fi
