#!/bin/bash
set -euo pipefail

ROOT="${PLEIADES_GENTOO_ROOT:-/workspaces/gentoo/root.x86_64}"
TMUX_SESSION="${PLEIADES_GENTOO_TMUX_SESSION:-gentoo}"
TMUX_SOCKET="${PLEIADES_GENTOO_TMUX_SOCKET:-pleiades-gentoo}"
LOG="${PLEIADES_GENTOO_HEARTBEAT_LOG:-/var/log/pleiades-gentoo-heartbeat.log}"
STATUS="${PLEIADES_GENTOO_HEARTBEAT_STATUS:-/run/pleiades-gentoo-heartbeat/status}"
LOCK="/run/pleiades-gentoo-heartbeat/lock"
HOSTNAME="${PLEIADES_GENTOO_HOSTNAME:-gentoo-codespace}"
UNDERHALL="${PLEIADES_GENTOO_UNDERHALL:-/workspaces/underhall}"

SERVICES=(
  taygete-omniversal.service
  alcyone-omniversal.service
  pleiades-rebirth-omniversal.service
  pleiades-atlas-omniversal.service
  celaeno-omniversal.service
  electra-omniversal.service
  pleiades-nexus-omniversal.service
  maia.service
  host-bridge-monitor.service
  windows-host-bridge-monitor.service
  pleiades-adaptive-builder.service
  pleiades-request-broker.service
  pleiades-forensic-scanner.service
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
        printf 'bridge_proc=%s\n' "$(bridge_state 'test -r /host/proc/1/status')"
        printf 'bridge_sys=%s\n' "$(bridge_state 'test -r /host/sys/kernel/uevent_seqnum')"
        printf 'bridge_run=%s\n' "$(bridge_state 'test -e /host/run/systemd')"
        printf 'bridge_mnt_c=%s\n' "$(bridge_state 'test -e /host/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe')"
        printf 'last_result=%s\n' "${1:-unknown}"
    } > "$STATUS"
}

container_nspawn_pid() {
    pgrep -f "^(/usr/bin/)?systemd-nspawn.*-D ${ROOT}( |$)" 2>/dev/null | grep -v "$$" \
        | sort -n \
        | tail -1
}

container_pid() {
    local nspawn inner
    nspawn="$(container_nspawn_pid || true)"
    if [[ -n "$nspawn" ]]; then
        inner="$(pgrep -P "$nspawn" 2>/dev/null | head -1 || true)"
        if [[ -n "$inner" ]]; then
            printf '%s\n' "$inner"
            return 0
        fi
    fi

    # Legacy fallback for payloads left under the heartbeat service cgroup.
    ps -eo pid=,comm=,cgroup= \
        | awk '$2 == "systemd" && $0 ~ /pleiades-gentoo-heartbeat.service\/payload\/init.scope/ {print $1; exit}'
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

    if tmux -L "$TMUX_SOCKET" has-session -t "$TMUX_SESSION" 2>/dev/null; then
        tmux -L "$TMUX_SOCKET" kill-session -t "$TMUX_SESSION" 2>/dev/null || true
    fi

    local cmd bind_args
    bind_args=(
        --bind-ro=/proc:/host/proc
        --bind-ro=/sys:/host/sys
        --bind-ro=/run:/host/run
    )
    [[ -d /mnt/c ]] && bind_args+=(--bind-ro=/mnt/c:/host/mnt/c)
    [[ -d "$UNDERHALL" ]] && bind_args+=(--bind="$UNDERHALL:/mnt/underhall")

    cmd=$(printf '%q ' sudo systemd-nspawn -D "$ROOT" \
        --register=no --resolv-conf=copy-host \
        --hostname="$HOSTNAME" "${bind_args[@]}" --boot)
    tmux -L "$TMUX_SOCKET" new-session -d -s "$TMUX_SESSION" "$cmd" 9>&-
    log "CONTAINER_START_REQUESTED|session=$TMUX_SESSION|root=$ROOT"
}

ensure_container() {
    CONTAINER_PID="$(container_pid || true)"
    if [[ -z "${CONTAINER_PID:-}" ]]; then
        if tmux -L "$TMUX_SOCKET" has-session -t "$TMUX_SESSION" 2>/dev/null; then
            log "WARN|tmux-session-stale|restarting"
        else
            log "WARN|tmux-session-missing|restarting"
        fi
        start_container || return 1
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

# ------------------------------------------------------------------
# Task #1: Persistent systemd mount units for host bridges
# These ensure bridges survive container restarts and WSL reboots
# ------------------------------------------------------------------
ensure_persistent_mount_units() {
    local unit_dir="$ROOT/etc/systemd/system"
    local wanted_dir="$ROOT/etc/systemd/system/multi-user.target.wants"
    mkdir -p "$unit_dir" "$wanted_dir"

    # proc bridge — host-proc.mount
    if [[ ! -f "$unit_dir/host-proc.mount" ]]; then
        cat > "$unit_dir/host-proc.mount" << 'MOUNT'
[Unit]
Description=Pleiades Host Proc Bridge
Before=local-fs.target

[Mount]
What=proc
Where=/host/proc
Type=proc
Options=ro,nosuid,nodev,noexec,noatime

[Install]
WantedBy=multi-user.target
MOUNT
        ln -sf "$unit_dir/host-proc.mount" "$wanted_dir/" 2>/dev/null || true
        log "MOUNT_UNIT_CREATED|host-proc.mount"
    fi

    # sys bridge — host-sys.mount
    if [[ ! -f "$unit_dir/host-sys.mount" ]]; then
        cat > "$unit_dir/host-sys.mount" << 'MOUNT'
[Unit]
Description=Pleiades Host Sys Bridge
Before=local-fs.target

[Mount]
What=sysfs
Where=/host/sys
Type=sysfs
Options=ro,nosuid,nodev,noexec,noatime

[Install]
WantedBy=multi-user.target
MOUNT
        ln -sf "$unit_dir/host-sys.mount" "$wanted_dir/" 2>/dev/null || true
        log "MOUNT_UNIT_CREATED|host-sys.mount"
    fi

    # run bridge — host-run.mount
    if [[ ! -f "$unit_dir/host-run.mount" ]]; then
        # Note: bind mounts can't be expressed as simple .mount units for rbind
        # We keep this as a post-boot mount via the heartbeat or a oneshot
        cat > "$unit_dir/host-run-bind.service" << 'SERVICE'
[Unit]
Description=Pleiades Host Run Bridge (rbind)
After=local-fs.target
Before=pleiades-host-bridge-finish.target
DefaultDependencies=no

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/mount --rbind /run /host/run
ExecStart=/bin/mount -o remount,bind,ro,nosuid,nodev /host/run
ExecStop=/bin/umount -R /host/run 2>/dev/null || true

[Install]
WantedBy=multi-user.target
SERVICE
        ln -sf "$unit_dir/host-run-bind.service" "$wanted_dir/" 2>/dev/null || true
        log "MOUNT_UNIT_CREATED|host-run-bind.service"
    fi

    # windows c: bridge — host-mnt-c.mount  
    if [[ ! -f "$unit_dir/host-mnt-c.mount" ]]; then
        cat > "$unit_dir/host-mnt-c.mount" << 'MOUNT'
[Unit]
Description=Pleiades Windows C: Bridge
Before=local-fs.target
ConditionPathExists=/mnt/c/Windows

[Mount]
What=/mnt/c
Where=/host/mnt/c
Type=none
Options=bind,ro

[Install]
WantedBy=multi-user.target
MOUNT
        ln -sf "$unit_dir/host-mnt-c.mount" "$wanted_dir/" 2>/dev/null || true
        log "MOUNT_UNIT_CREATED|host-mnt-c.mount"
    fi

    # Enable all mount units inside container
    nsenter -t "$CONTAINER_PID" -m -u -i -n -p -- systemctl daemon-reload 2>/dev/null || true
    nsenter -t "$CONTAINER_PID" -m -u -i -n -p -- systemctl enable host-proc.mount host-sys.mount host-run-bind.service host-mnt-c.mount 2>/dev/null || true
    log "MOUNT_UNITS_ENABLED|container-pid=$CONTAINER_PID"
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

bridge_state() {
    local check="$1"
    if [[ -n "${CONTAINER_PID:-}" ]] && kill -0 "$CONTAINER_PID" 2>/dev/null && inside bash -lc "$check" >/dev/null 2>&1; then
        echo mounted
    else
        echo absent
    fi
}

container_required_bridges_ready() {
    inside bash -lc 'test -r /host/proc/1/status && test -r /host/sys/kernel/uevent_seqnum && test -e /host/run/systemd'
}

ensure_windows_bridge_monitor_unit() {
    if ! inside bash -lc 'test -x /usr/local/bin/windows_host_bridge_monitor.sh && test -e /host/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe' >/dev/null 2>&1; then
        return 0
    fi

    if ! inside systemctl cat windows-host-bridge-monitor.service >/dev/null 2>&1; then
        inside bash -lc 'cat > /etc/systemd/system/windows-host-bridge-monitor.service << "SERVICE"
[Unit]
Description=Pleiades Windows Host Read-Only Bridge Monitor
After=network.target host-bridge-monitor.service

[Service]
Type=simple
ExecStart=/usr/local/bin/windows_host_bridge_monitor.sh
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
SERVICE
systemctl daemon-reload
systemctl enable windows-host-bridge-monitor.service >/dev/null 2>&1' \
            && log "SERVICE_INSTALLED|windows-host-bridge-monitor.service" \
            || log "WARN|service-install-failed|windows-host-bridge-monitor.service"
    fi
}

archive_container_telemetry() {
    [[ -n "${CONTAINER_PID:-}" ]] && kill -0 "$CONTAINER_PID" 2>/dev/null || return 0
    inside bash -lc '
set -euo pipefail
src=/run/pleiades/pleiades-nexus_fifo
archive_dir=/var/lib/pleiades/archive
[[ -s "$src" ]] || exit 0
mkdir -p "$archive_dir"
chmod 0750 "$archive_dir" 2>/dev/null || true
stamp=$(date -u +%Y%m%dT%H%M%SZ)
out="$archive_dir/pleiades-nexus_${stamp}_$$.log"
cp -- "$src" "$out"
chmod 0640 "$out" 2>/dev/null || true
: > "$src"
printf "ARCHIVED|%s\n" "$out" >> "$src"
find "$archive_dir" -maxdepth 1 -type f -name "pleiades-nexus_*.log" -mtime +14 -delete 2>/dev/null || true
' \
        && log "ARCHIVED" \
        || log "WARN|telemetry-archive-failed"
}

restart_container_for_bridges() {
    local old_pid="$CONTAINER_PID" nspawn i
    log "WARN|container-bridges-missing|restarting-container"

    archive_container_telemetry
    inside systemctl poweroff --no-wall >/dev/null 2>&1 || true
    for i in $(seq 1 30); do
        sleep 1
        if ! kill -0 "$old_pid" 2>/dev/null; then
            break
        fi
    done

    nspawn="$(container_nspawn_pid || true)"
    if [[ -n "$nspawn" ]]; then
        kill "$nspawn" >/dev/null 2>&1 || true
        sleep 2
        kill -9 "$nspawn" >/dev/null 2>&1 || true
    fi
    tmux -L "$TMUX_SOCKET" kill-session -t "$TMUX_SESSION" >/dev/null 2>&1 || true

    start_container || return 1
    for i in $(seq 1 90); do
        sleep 1
        CONTAINER_PID="$(container_pid || true)"
        if [[ -n "${CONTAINER_PID:-}" ]] && kill -0 "$CONTAINER_PID" 2>/dev/null; then
            if container_required_bridges_ready >/dev/null 2>&1; then
                log "CONTAINER_READY|pid=$CONTAINER_PID|bridges=ok|wait=${i}s"
                return 0
            fi
        fi
    done
    log "ERROR|container-bridge-restart-timeout"
    return 1
}

check_container_services() {
    local svc state
    ensure_windows_bridge_monitor_unit
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
    inside bash -lc 'mkdir -p /run/pleiades; touch /run/pleiades/pleiades-nexus_fifo; test -d /scripts; test -e /host/proc/1/status; test -e /host/sys/kernel/uevent_seqnum; test -e /host/run/systemd' \
        && log "READY_PATHS_OK" \
        || log "WARN|ready-path-check-failed"
    inside bash -lc 'test -e /host/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe' \
        && log "WINDOWS_BRIDGE_OK" \
        || log "WINDOWS_BRIDGE_DEGRADED|windows-path-not-detected"
}

main() {
    local result="ok"
    ensure_container || result="container-error"
    ensure_bridges || true

    # Task #1: Create persistent mount units inside container
    if [[ "${result}" == "ok" ]] && [[ -n "${CONTAINER_PID:-}" ]]; then
        ensure_persistent_mount_units || true
    fi

    if [[ "${result}" == "ok" ]]; then
        container_required_bridges_ready >/dev/null 2>&1 || restart_container_for_bridges || result="bridge-error"
    fi
    if [[ "${result}" == "ok" ]]; then
        check_container_ready_paths || true
        archive_container_telemetry || true
        check_container_services || true
    fi
    write_status "$result"
    log "PULSE_COMPLETE|result=$result|pid=${CONTAINER_PID:-absent}"
    rotate_log
    [[ "$result" == "ok" ]]
}

main "$@"
