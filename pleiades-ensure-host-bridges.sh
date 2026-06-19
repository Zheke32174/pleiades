#!/bin/bash
source "${PLEIADES_TERMUX_LIB:-}" 2>/dev/null || true
# pleiades-ensure-host-bridges.sh
# Mounts the four host-bridge bind points used by the Gentoo nspawn container.
# Idempotent: skips already-mounted targets.
# Runs at WSL boot (via pleiades-host-bridges.service) and on container restart.

set -euo pipefail

# Termux: this script manages systemd-nspawn host bridges (not applicable)
[[ "${PLEIADES_ENV:-}" == "termux" ]] && echo "[pleiades-bridges] Termux: no systemd-nspawn, skipping" && exit 0

ROOT="${PLEIADES_GENTOO_ROOT:-${PLEIADES_ROOT:-${HOME}/pleiades}/rootfs}"
LOG=/var/log/pleiades-gentoo-heartbeat.log

_log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) PLEIADES_BRIDGES|$*" | tee -a "$LOG" 2>/dev/null || true; }

ensure_dir() { mkdir -p "$1" 2>/dev/null || true; }

mount_bridge() {
    local label="$1" target="$2"; shift 2
    ensure_dir "$target"
    if mountpoint -q "$target" 2>/dev/null; then
        _log "PRESENT|$label|$target"
        return 0
    fi
    if "$@"; then
        _log "MOUNTED|$label|$target"
        return 0
    fi
    _log "WARN|mount-failed|$label|$target"
    return 1
}

mount_proc() {
    mount -t proc proc "$ROOT/host/proc" -o ro,nosuid,nodev,noexec,noatime
}

mount_sys() {
    mount -t sysfs sysfs "$ROOT/host/sys" -o ro,nosuid,nodev,noexec,noatime
}

mount_run() {
    mount --rbind /run "$ROOT/host/run" && \
        mount -o remount,bind,ro,nosuid,nodev "$ROOT/host/run"
}

mount_windows() {
    [[ -d /mnt/c ]] || { _log "SKIP|mnt/c not available"; return 1; }
    mount --bind /mnt/c "$ROOT/host/mnt/c" && \
        mount -o remount,bind,ro "$ROOT/host/mnt/c"
}

ensure_dir "$ROOT/host/proc"
ensure_dir "$ROOT/host/sys"
ensure_dir "$ROOT/host/run"
ensure_dir "$ROOT/host/mnt/c"

mount_bridge host-proc   "$ROOT/host/proc"   mount_proc    || true
mount_bridge host-sys    "$ROOT/host/sys"    mount_sys     || true
mount_bridge host-run    "$ROOT/host/run"    mount_run     || true
mount_bridge host-mnt-c  "$ROOT/host/mnt/c"  mount_windows || true

_log "DONE|root=$ROOT"
