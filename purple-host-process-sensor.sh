#!/bin/bash
set -euo pipefail

RUN_DIR="${PURPLE_HOST_CAPSULE_RUN:-/run/purple-host-capsule}"
STATE_DIR="${PURPLE_HOST_CAPSULE_STATE:-/var/lib/purple-host-capsule}"
SUMMARY="$RUN_DIR/process-summary"
ALERTS="$RUN_DIR/process-alerts.jsonl"
STATUS="$RUN_DIR/status"
LOCK="$RUN_DIR/lock"
POLICY="/etc/purple/host-bridge-policy.json"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    exec sudo -E "$0" "$@"
fi

mkdir -p "$RUN_DIR" "$STATE_DIR"
exec 9>"$LOCK"
flock -n 9 || exit 0

event() {
    local category="$1" pid="$2" name="$3" score="$4" reason="$5" cmd="$6"
    local ts
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    
    # Seen cache to avoid duplicate alerts in the same session
    local cache_key
    cache_key=$(printf "%s|%s" "$pid" "$cmd" | sha256sum | cut -d" " -f1)
    if grep -q "$cache_key" "$RUN_DIR/seen_alerts" 2>/dev/null; then
        return 0
    fi
    echo "$cache_key" >> "$RUN_DIR/seen_alerts"

    jq -c -n --arg ts "$ts" --arg cat "$category" --arg pid "$pid" \
          --arg name "$name" --arg score "$score" --arg reason "$reason" \
          --arg cmd "$cmd" \
          '{schema: "purple-host-process-alert-v1", updated_utc: $ts, category: $cat, pid: ($pid|tonumber), name: $name, score: ($score|tonumber), reason: $reason, cmdline: $cmd}' \
          >> "$ALERTS"
}

rotate_alerts() {
    local max_lines=10000
    if [[ -f "$ALERTS" ]] && [[ $(wc -l < "$ALERTS") -gt $max_lines ]]; then
        local tmp
        tmp=$(mktemp)
        tail -n "$((max_lines / 2))" "$ALERTS" > "$tmp"
        mv "$tmp" "$ALERTS"
    fi
    # Clear seen alerts daily
    local today
    today=$(date +%Y%m%d)
    if [[ ! -f "$RUN_DIR/cache_cleared_$today" ]]; then
        rm -f "$RUN_DIR/seen_alerts"
        touch "$RUN_DIR/cache_cleared_$today"
    fi
}

score_process() {
    local pid="$1" name="$2" ppid="$3" state="$4" cmd="$5"
    local lcmd lname score=0 category="" reason=""
    lcmd="${cmd,,}"
    lname="${name,,}"

    case "$lcmd" in
        *"ssh -r "*|*"ssh.exe -r "*|*" -r 127.0.0.1"*|*" -d "*)
            score=$((score + 35)); category="reverse_tunnel"; reason="${reason}ssh-reverse-or-dynamic-tunnel;" ;;
    esac
    case "$lcmd" in
        *chisel*|*plink*|*stowaway*|*rsockstun*|*frp*|*ngrok*|*cloudflared*|*ligolo*|*socat*tcp-listen*|*"nc -e"*|*"ncat -e"*|*"bash -i"*|*"/dev/tcp/"*)
            score=$((score + 45)); category="${category:-tunnel_or_reverse_shell}"; reason="${reason}tunnel-or-shell-pattern;" ;;
    esac
    case "$lcmd" in
        *powershell*|*pwsh*|*wmic*|*wmi*|*schtasks*|*rundll32*|*reg.exe*)
            score=$((score + 20)); category="${category:-windows_lolbin}"; reason="${reason}windows-admin-or-lolbin;" ;;
    esac
    case "$lcmd" in
        *nsenter*|*systemd-nspawn*|*machinectl*|*"wsl.exe"*|*"docker exec"*|*"kubectl exec"*)
            score=$((score + 25)); category="${category:-container_boundary}"; reason="${reason}container-boundary-tool;" ;;
    esac
    case "$lcmd" in
        *"/etc/ld.so.preload"*|*"authorized_keys"*|*"crontab"*|*"/etc/systemd/system"*|*"systemctl enable"*)
            score=$((score + 20)); category="${category:-persistence_probe}"; reason="${reason}persistence-path-reference;" ;;
    esac

    if (( score > 0 )); then
        event "$category" "$pid" "$name" "$score" "$reason" "$cmd"
    fi
}

collect() {
    local tmp
    tmp="$(mktemp "$RUN_DIR/process-summary.XXXXXX")"
    {
        echo "schema=purple-host-process-summary-v1"
        echo "updated_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "policy=$POLICY"
        echo "mode=read-only-sensor"
        echo "authority=observe-and-report"
        echo "owner_visible=yes"
        echo "--- top_cpu ---"
        ps -eo pid,ppid,state,comm,pcpu,pmem,args --sort=-pcpu 2>/dev/null | head -25 || true
        echo "--- listeners ---"
        ss -ltnup 2>/dev/null || netstat -ltnup 2>/dev/null || true
        echo "--- suspicious_recent ---"
        tail -50 "$ALERTS" 2>/dev/null || true
    } > "$tmp"
    mv "$tmp" "$SUMMARY"

    ps -eo pid=,ppid=,state=,comm=,args= 2>/dev/null | while read -r pid ppid state name cmd; do
        [[ -n "${pid:-}" ]] || continue
        score_process "$pid" "$name" "$ppid" "$state" "$cmd"
    done

    {
        echo "updated_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "summary=$SUMMARY"
        echo "alerts=$ALERTS"
        echo "last_result=ok"
    } > "$STATUS"
}

rotate_alerts
collect
