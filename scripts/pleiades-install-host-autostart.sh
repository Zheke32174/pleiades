#!/usr/bin/env bash
# =============================================================================
# pleiades-install-host-autostart.sh
#
# Installs the Windows-login→WSL→Gentoo container auto-start chain so the
# Pleiades nspawn container boots automatically when you log into Windows.
#
# Three layers — each fails independently:
#   1. Windows Startup (VBS) — triggers WSL and keeps it alive at login
#   2. WSL systemd service  — starts the container reliably at WSL boot
#   3. wsl.conf [boot]      — fallback if systemd service doesn't fire
#
# Usage:
#   bash scripts/pleiades-install-host-autostart.sh [--dry-run] [--uninstall]
#
# Run from: the WSL host (any directory with sudo access).
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_TAG="pleiades-autostart"

DRY_RUN=false
UNINSTALL=false
for arg in "$@"; do
  [[ "$arg" == "--dry-run" ]]  && DRY_RUN=true
  [[ "$arg" == "--uninstall" ]] && UNINSTALL=true
done

log()  { echo "[$LOG_TAG] $*"; }
run()  { if $DRY_RUN; then echo "[DRY-RUN] $*"; else "$@"; fi; }
die()  { echo "ERROR: $*" >&2; exit 1; }

[[ "${EUID:-$(id -u)}" -ne 0 ]] && die "Must run as root (try: sudo bash $0)"

# ────────────────────────────────────────────────────────────────────────────
# Uninstall
# ────────────────────────────────────────────────────────────────────────────
if $UNINSTALL; then
  log "Uninstalling Pleiades host auto-start..."

  # Systemd service
  if systemctl is-enabled pleiades-container.service &>/dev/null 2>&1; then
    run systemctl stop    pleiades-container.service 2>/dev/null || true
    run systemctl disable pleiades-container.service 2>/dev/null || true
    log "Disabled pleiades-container.service"
  fi
  run rm -f /etc/systemd/system/pleiades-container.service
  run systemctl daemon-reload 2>/dev/null || true

  # wsl.conf boot command
  if [[ -f /etc/wsl.conf ]]; then
    # Remove the pleiades-specific boot command line from [boot] section
    if grep -q "pleiades-wsl-boot" /etc/wsl.conf 2>/dev/null; then
      run sed -i '/^command=.*pleiades-wsl-boot/d' /etc/wsl.conf
      log "Removed pleiades boot command from /etc/wsl.conf"
    fi
  fi

  # VBS Startup script
  VBS_PATH="/mnt/c/Users/Fixxia/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/Pleiades-WSL-Start.vbs"
  if [[ -f "$VBS_PATH" ]]; then
    run rm -f "$VBS_PATH"
    log "Removed $VBS_PATH"
  fi

  log "Uninstall complete."
  log "NOTE: Full cleanup requires 'wsl --shutdown' to take effect."
  exit 0
fi

# ────────────────────────────────────────────────────────────────────────────
# Detect environment
# ────────────────────────────────────────────────────────────────────────────
IS_WSL=false
grep -qi microsoft /proc/version 2>/dev/null && IS_WSL=true

log "Detected environment: $($IS_WSL && echo 'WSL' || echo 'bare metal')"

WINDOWS_USER="Fixxia"
WINDOWS_PROFILE="/mnt/c/Users/$WINDOWS_USER"
if [[ ! -d "$WINDOWS_PROFILE" ]]; then
  # Auto-detect Windows user
  WINDOWS_USER=$(ls /mnt/c/Users/ 2>/dev/null | grep -v "^Public$\|^Default$\|^All Users" | head -1)
  WINDOWS_PROFILE="/mnt/c/Users/$WINDOWS_USER"
fi
log "Windows user: $WINDOWS_USER"

VBS_DIR="$WINDOWS_PROFILE/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup"
VBS_PATH="$VBS_DIR/Pleiades-WSL-Start.vbs"

# ────────────────────────────────────────────────────────────────────────────
# Layer 1: Windows Startup VBS
# ────────────────────────────────────────────────────────────────────────────
install_vbs() {
  log "=== Layer 1: Windows Startup VBS ==="

  if $DRY_RUN; then
    log "[DRY-RUN] Would write VBS to: $VBS_PATH"
    return
  fi

  if [[ ! -d "$VBS_DIR" ]]; then
    log "WARNING: Windows Startup directory not found at $VBS_DIR"
    log "WARNING: Skipping VBS install — Task Scheduler fallback available"
    return
  fi

  # WSL distro autodetection
  WSL_DISTRO="Ubuntu"
  if command -v wsl.exe &>/dev/null; then
    DETECTED=$(wsl.exe --list --quiet 2>/dev/null | head -1 | tr -d '\r\n')
    [[ -n "$DETECTED" ]] && WSL_DISTRO="$DETECTED"
  fi
  log "WSL distro: $WSL_DISTRO"

  # Write VBS that runs 'sleep infinity' as the normal user to keep WSL alive
  cat > "$VBS_PATH" << VBS_EOF
' Pleiades-WSL-Start.vbs — starts WSL silently and keeps it alive
' Installed by pleiades-install-host-autostart.sh
'
' Runs 'sleep infinity' as the normal user so WSL stays running in the
' background. The [boot] command or systemd service starts the container.
CreateObject("WScript.Shell").Run "wsl -d ${WSL_DISTRO} -u ${WINDOWS_USER} bash -c ""sleep infinity & wait""", 0, False
VBS_EOF

  chmod 644 "$VBS_PATH"
  log "Wrote: $VBS_PATH"
  log "Content: wsl -d ${WSL_DISTRO} -u ${WINDOWS_USER} bash -c 'sleep infinity & wait'"
}

# ────────────────────────────────────────────────────────────────────────────
# Layer 2: systemd service (WSL host)
# ────────────────────────────────────────────────────────────────────────────
install_service() {
  log "=== Layer 2: systemd service ==="

  local SERVICE_FILE="/etc/systemd/system/pleiades-container.service"
  local BOOT_SCRIPT="/usr/local/bin/pleiades-wsl-boot.sh"
  local BOOT_SOURCE="$WORKSPACE/root.x86_64/usr/local/bin/pleiades-wsl-boot.sh"

  # Ensure boot script is deployed
  if [[ -f "$BOOT_SCRIPT" ]]; then
    log "Boot script already exists: $BOOT_SCRIPT"
  elif [[ -f "$BOOT_SOURCE" ]]; then
    run cp "$BOOT_SOURCE" "$BOOT_SCRIPT"
    run chmod 755 "$BOOT_SCRIPT"
    log "Deployed boot script from container copy"
  else
    # Write from scratch
    log "Writing boot script from template..."
    run cat > "$BOOT_SCRIPT" << 'BOOTSCRIPT'
#!/usr/bin/env bash
# pleiades-wsl-boot.sh — WSL boot-time container launcher
# Runs as root from systemd service or wsl.conf [boot] command.
set -uo pipefail
GENTOO_ROOT=/workspaces/gentoo/root.x86_64
if [ ! -d "$GENTOO_ROOT" ]; then echo "[pleiades-wsl-boot] rootfs not found"; exit 0; fi
if pgrep -x systemd-nspawn >/dev/null 2>&1; then echo "[pleiades-wsl-boot] already running"; exit 0; fi
if ! mountpoint -q /run/systemd/nspawn 2>/dev/null; then
  mkdir -p /run/systemd/nspawn
  mount -t tmpfs tmpfs /run/systemd/nspawn
fi
BIND_ARGS=()
[ -d /workspaces/underhall ] && BIND_ARGS+=(--bind=/workspaces/underhall:/mnt/underhall)
exec systemd-nspawn -D "$GENTOO_ROOT" --register=no --keep-unit --resolv-conf=copy-host --hostname=gentoo-codespace ${BIND_ARGS[@]} --boot
BOOTSCRIPT
    run chmod 755 "$BOOT_SCRIPT"
    log "Wrote boot script from template"
  fi

  # Write service unit
  run cat > "$SERVICE_FILE" << SERVICE
[Unit]
Description=Pleiades Gentoo nspawn container
Documentation=https://github.com/Zheke32174/pleiades
After=local-fs.target network.target
Before=shutdown.target
Wants=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=${BOOT_SCRIPT}
ExecStop=/usr/local/bin/gentoo-down
TimeoutStartSec=120
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
SERVICE

  run systemctl daemon-reload
  run systemctl enable pleiades-container.service
  log "Service enabled: pleiades-container.service"
}

# ────────────────────────────────────────────────────────────────────────────
# Layer 3: wsl.conf boot command fallback
# ────────────────────────────────────────────────────────────────────────────
install_wslconf() {
  log "=== Layer 3: wsl.conf fallback ==="

  if ! $IS_WSL; then
    log "Not WSL — skipping wsl.conf"
    return
  fi

  local WSL_CONF="/etc/wsl.conf"
  local BOOT_SCRIPT="/usr/local/bin/pleiades-wsl-boot.sh"

  if [[ -f "$WSL_CONF" ]] && grep -q "pleiades-wsl-boot" "$WSL_CONF" 2>/dev/null; then
    log "wsl.conf already has pleiades boot command — skipping"
    return
  fi

  if $DRY_RUN; then
    log "[DRY-RUN] Would add [boot] command to $WSL_CONF"
    return
  fi

  # Ensure wsl.conf has [boot] with command + systemd=true
  local TMP_CONF=$(mktemp)
  if [[ -f "$WSL_CONF" ]]; then
    # Preserve existing content, update or add [boot] section
    if grep -q '^\[boot\]' "$WSL_CONF"; then
      # Add command line after [boot] header if not already there
      if ! grep -q "^command=" "$WSL_CONF" 2>/dev/null; then
        sed '/^\[boot\]/a\command='"$BOOT_SCRIPT" "$WSL_CONF" > "$TMP_CONF"
        cp "$TMP_CONF" "$WSL_CONF"
        log "Added boot command to existing [boot] section"
      fi
    else
      printf '\n[boot]\nsystemd=true\ncommand=%s\n' "$BOOT_SCRIPT" >> "$WSL_CONF"
      log "Appended [boot] section to $WSL_CONF"
    fi
  else
    cat > "$WSL_CONF" << WSLCONF
[boot]
systemd=true
command=${BOOT_SCRIPT}
WSLCONF
    log "Created $WSL_CONF with systemd=true and boot command"
  fi
  rm -f "$TMP_CONF"
}

# ────────────────────────────────────────────────────────────────────────────
# Verify
# ────────────────────────────────────────────────────────────────────────────
verify() {
  log "=== Verification ==="
  local ALL_OK=true

  echo ""
  echo "  [VBS] $VBS_PATH"
  if [[ -f "$VBS_PATH" ]]; then
    echo "        ✅ Present"
    echo "        Content: $(head -1 "$VBS_PATH")"
  else
    echo "        ❌ Missing"
    ALL_OK=false
  fi

  echo "  [Service] /etc/systemd/system/pleiades-container.service"
  if [[ -f /etc/systemd/system/pleiades-container.service ]]; then
    echo "           ✅ Present"
    local SVC_STATE=$(systemctl is-enabled pleiades-container.service 2>/dev/null || echo "unknown")
    echo "           Status: $SVC_STATE"
  else
    echo "           ❌ Missing"
    ALL_OK=false
  fi

  echo "  [Boot] /usr/local/bin/pleiades-wsl-boot.sh"
  if [[ -f /usr/local/bin/pleiades-wsl-boot.sh ]]; then
    echo "        ✅ Present ($(wc -l < /usr/local/bin/pleiades-wsl-boot.sh) lines)"
    bash -n /usr/local/bin/pleiades-wsl-boot.sh 2>/dev/null && echo "        Syntax: ✅" || { echo "        Syntax: ❌"; ALL_OK=false; }
  else
    echo "        ❌ Missing"
    ALL_OK=false
  fi

  echo "  [wsl.conf] /etc/wsl.conf (fallback)"
  if [[ -f /etc/wsl.conf ]]; then
    echo "            ✅ Present"
    grep -q "pleiades-wsl-boot" /etc/wsl.conf 2>/dev/null && echo "            Boot command: ✅" || echo "            Boot command: ⚠️  Not set"
  else
    echo "            ❌ Missing"
    ALL_OK=false
  fi

  echo ""
  if $ALL_OK; then
    log "✅ All layers installed."
    log "NOTE: Changes take effect after 'wsl --shutdown' + Windows logoff/logon."
    log "      To test now: run 'sudo systemctl start pleiades-container.service'"
  else
    log "❌ Some checks failed — review above."
  fi
}

# ────────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────────
log "╔═══════════════════════════════════════════════════════════════╗"
log "║  Pleiades Host Auto-Start Installer                          ║"
log "╚═══════════════════════════════════════════════════════════════╝"
log ""

install_vbs
install_service
install_wslconf

log ""
verify
log ""
log "Done. Run 'wsl --shutdown && wsl' to test."
