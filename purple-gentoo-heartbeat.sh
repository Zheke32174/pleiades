#!/bin/bash
set -euo pipefail

ROOT="${PURPLE_GENTOO_ROOT:-/workspaces/gentoo/root.x86_64}"
TMUX_SESSION="${PURPLE_GENTOO_TMUX_SESSION:-gentoo}"
LOG="${PURPLE_GENTOO_HEARTBEAT_LOG:-/var/log/purple-gentoo-heartbeat.log}"
STATUS="${PURPLE_GENTOO_HEARTBEAT_STATUS:-/run/purple-gentoo-heartbeat/status}"
LOCK="/run/purple-gentoo-heartbeat/lock"
HOSTNAME="${PURPLE_GENTOO_HOSTNAME:-gentoo-codespace}"
UNDERHALL="${PURPLE_GENTOO_UNDERHALL:-/workspaces/underhall}"

SERVICES=(
  cheshire-omniversal.service
  hatter-omniversal.service
  resurrection-omniversal.service
  zod-omniversal.service
  little-john-omniversal.service
  robin-omniversal.service
  ouroboros-omniversal.service
  sophia.service
  host-bridge-monitor.service
  windows-host-bridge-monitor.service
  purple-adaptive-builder.service
  purple-request-broker.service
)

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    exec sudo -E "$0" "$@"
fi

mkdir -p "$(dirname "$LOG")" "$(dirname "$STATUS")"
exec 9>"$LOCK"
if ! flock -n 9; then
    exit 0
fi


rotate_log() {
    local max_lines=5000
    if [[ -f "$LOG" ]] && [[ $(wc -l < "$LOG") -gt $max_lines ]]; then
        local tmp
        tmp=$(mktemp)
        tail -n "$((max_lines / 2))" "$LOG" > "$tmp"
        mv "$tmp" "$LOG"
    fi
}

log() {
    local line
    line="$(date -u +%Y-%m-%dT%H:%M:%SZ)|$*"
    printf '%s\n' "$line" | tee -a "$LOG" >/dev/null
}

write_status() {
    {
        printf 'updated_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        printf 'root=%s\n' "$ROOT"
        printf 'tmux_session=%s\n' "$TMUX_SESSION"
        printf 'container_pid=%s\n' "${CONTAINER_PID:-absent}"
        printf 'bridge_proc=%s\n' "$(mountpoint -q "$ROOT/host/proc" && echo mounted || echo absent)"
        printf 'bridge_sys=%s\n' "$(mountpoint -q "$ROOT/host/sys" && echo mounted || echo absent)"
        printf 'bridge_run=%s\n' "$(mountpoint -q "$ROOT/host/run" && echo mounted || echo absent)"
        printf 'bridge_mnt_c=%s\n' "$(mountpoint -q "$ROOT/host/mnt/c" && echo mounted || echo absent)"
        printf 'last_result=%s\n' "${1:-unknown}"
    } > "$STATUS"
}

container_pid() {
    pgrep -f "^(/usr/bin/)?systemd-nspawn.*-D ${ROOT}( |$)" 2>/dev/null | grep -v "$$" \
        | sort -n \
        | tail -1
}

start_container() {
    if [[ ! -d "$ROOT" ]]; then
        log "ERROR|root-missing|$ROOT"
        return 1
    fi
    if ! command -v systemd-nspawn >/dev/null 2>&1; then
        log "ERROR|systemd-nspawn-missing"
        return 1
    fi
    if ! command -v tmux >/dev/null 2>&1; then
        log "ERROR|tmux-missing"
        return 1
    fi

    if tmux has-session -t "$TMUX_SESSION" 2>/dev/null; then
        tmux -L purple-gentoo kill-session -t "$TMUX_SESSION" 2>/dev/null || true
    fi

    local cmd
    cmd=$(printf '%q ' sudo systemd-nspawn -D "$ROOT" \
        --register=no --keep-unit --resolv-conf=copy-host \
        --hostname="$HOSTNAME" --bind="$UNDERHALL:/mnt/underhall" --boot)
    tmux -L purple-gentoo new-session -d -s "$TMUX_SESSION" "$cmd"
    log "CONTAINER_START_REQUESTED|session=$TMUX_SESSION|root=$ROOT"
}

ensure_container() {
    CONTAINER_PID="$(container_pid || true)"
    if [[ -z "${CONTAINER_PID:-}" ]]; then
        if ! tmux -L purple-gentoo has-session -t "$TMUX_SESSION" 2>/dev/null; then
            log "WARN|tmux-session-missing|restarting"
            start_container || return 1
        fi
        # Re-check PID after potential start
        CONTAINER_PID="$(container_pid || true)"
    fi
    if [[ -n "${CONTAINER_PID:-}" ]] && kill -0 "$CONTAINER_PID" 2>/dev/null; then
        log "CONTAINER_PRESENT|pid=$CONTAINER_PID"
        return 0
    fi

    start_container || return 1
    local i
    for i in $(seq 1 90); do
        sleep 1
        CONTAINER_PID="$(container_pid || true)"
        if [[ -n "${CONTAINER_PID:-}" ]] && kill -0 "$CONTAINER_PID" 2>/dev/null; then
            log "CONTAINER_READY|pid=$CONTAINER_PID|wait=${i}s"
            return 0
        fi
    done
    log "ERROR|container-start-timeout"
    return 1
}

ensure_mount() {
    local label="$1" target="$2"
    shift 2
    mkdir -p "$target"
    if mountpoint -q "$target"; then
        log "BRIDGE_PRESENT|$label|$target"
        return 0
    fi
    if "$@"; then
        log "BRIDGE_MOUNTED|$label|$target"
        return 0
    fi
    log "WARN|bridge-mount-failed|$label|$target"
    return 1
}

mount_proc_bridge() {
    mount -t proc proc "$ROOT/host/proc" -o ro,nosuid,nodev,noexec,noatime
}

mount_sys_bridge() {
    mount -t sysfs sysfs "$ROOT/host/sys" -o ro,nosuid,nodev,noexec,noatime
}

mount_run_bridge() {
    mount --rbind /run "$ROOT/host/run" && mount -o remount,bind,ro,nosuid,nodev "$ROOT/host/run"
}

mount_windows_bridge() {
    [[ -d /mnt/c ]] || return 1
    mount --bind /mnt/c "$ROOT/host/mnt/c" && mount -o remount,bind,ro "$ROOT/host/mnt/c"
}

ensure_bridges() {
    mkdir -p "$ROOT/host/proc" "$ROOT/host/sys" "$ROOT/host/run" "$ROOT/host/mnt/c"
    ensure_mount host-proc "$ROOT/host/proc" mount_proc_bridge || true
    ensure_mount host-sys "$ROOT/host/sys" mount_sys_bridge || true
    ensure_mount host-run "$ROOT/host/run" mount_run_bridge || true
    ensure_mount windows-c "$ROOT/host/mnt/c" mount_windows_bridge || true
}

inside() {
    nsenter -t "$CONTAINER_PID" -m -u -i -n -p -- "$@"
}

check_container_services() {
    local svc state
    for svc in "${SERVICES[@]}"; do
        state="$(inside systemctl is-active "$svc" 2>/dev/null || true)"
        case "$state" in
            active)
                log "SERVICE_ACTIVE|$svc"
                ;;
            inactive|failed|deactivating|"")
                log "SERVICE_RECOVER|$svc|state=${state:-missing}"
                inside systemctl restart "$svc" >/dev/null 2>&1 || log "WARN|service-restart-failed|$svc"
                ;;
            activating)
                log "SERVICE_WAIT|$svc|state=activating"
                ;;
            *)
                log "SERVICE_STATE|$svc|$state"
                ;;
        esac
    done
}

check_container_ready_paths() {
    inside bash -lc 'mkdir -p /run/purple; touch /run/purple/ouroboros_fifo; test -d /scripts; test -e /host/proc/1/status; test -e /host/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe' \
        && log "READY_PATHS_OK" \
        || log "WARN|ready-path-check-failed"
}

main() {
    local result="ok"
    ensure_container || result="container-error"
    ensure_bridges || true
    if [[ "${result}" == "ok" ]]; then
        check_container_ready_paths || true
        check_container_services || true
    fi
    write_status "$result"
    log "PULSE_COMPLETE|result=$result|pid=${CONTAINER_PID:-absent}"
    rotate_log
    [[ "$result" == "ok" ]]
}

main "$@"
