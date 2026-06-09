#!/usr/bin/env bash
# ryz-compliance: 8263d5b8 shell
# Source configuration
source /etc/purple/pleiades.conf 2>/dev/null || source "$(dirname "$0")/../etc/purple/pleiades.conf"
# ==============================================================================
# pleiades-vscode-bridge.sh — VS Code Insiders Integration Bridge
#
# Bridges the pleiades ecosystem with VS Code Insiders running on the Windows host.
# Provides:
#   - Remote terminal access from VS Code to container shell
#   - File system bridge for editing container files from Windows
#   - Task integration (VS Code tasks can trigger pleiades events)
#   - Diagnostic forwarding (pleiades logs → VS Code Output panel)
# ==============================================================================

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLEIADES_CONTAINER_ROOT="${PLEIADES_CONTAINER_ROOT:-$(dirname "$SCRIPT_DIR")}"

# VS Code binary — auto-detect on WSL; override via PLEIADES_VSCODE_BIN env var
_detect_vscode_bin() {
    local win_user
    win_user="$(cmd.exe /c echo %USERNAME% 2>/dev/null | tr -d '\r' || true)"
    local candidates=(
        "${PLEIADES_VSCODE_BIN:-}"
        "/mnt/c/Users/${win_user}/AppData/Local/Programs/Microsoft VS Code Insiders/bin/code-insiders"
        "/mnt/c/Users/${win_user}/AppData/Local/Programs/Microsoft VS Code/bin/code"
        "$(command -v code-insiders 2>/dev/null || true)"
        "$(command -v code 2>/dev/null || true)"
    )
    for c in "${candidates[@]}"; do
        [[ -n "$c" && -x "$c" ]] && { echo "$c"; return; }
    done
    echo "code"  # fallback: hope it's on PATH
}
VSCODE_BIN="$(_detect_vscode_bin)"
BRIDGE_DIR="${PLEIADES_RUN_DIR}/vscode-bridge"
WORKSPACE_DIR="${HOME}/vscode-pleiades-workspace"
SHARED_LOCK="$BRIDGE_DIR/bridge.lock"
EVENT_FIFO="$BRIDGE_DIR/events.fifo"
VSCODE_SETTINGS="$WORKSPACE_DIR/.vscode/settings.json"
VSCODE_TASKS="$WORKSPACE_DIR/.vscode/tasks.json"
HEARTBEAT_FILE="$BRIDGE_DIR/heartbeat"

mkdir -p "$BRIDGE_DIR" "$WORKSPACE_DIR/.vscode" "$WORKSPACE_DIR/.vscode/extensions"

log() { logger -t pleiades-vscode "[$$] $*"; }

# ─── Generate VS Code Workspace Config ─────────────────────────────────────────
generate_workspace() {
    # VS Code settings — optimized for container development
    cat > "$VSCODE_SETTINGS" << 'SETTINGS'
{
    "terminal.integrated.defaultLocation": "editor",
    "terminal.integrated.cwd": "${PLEIADES_CONTAINER_ROOT}",
    "files.exclude": {
        "**/.git": true,
        "**/host/**": true
    },
    "files.watcherExclude": {
        "**/host/**": true,
        "**/.git/**": true,
        "**/var/lib/pleiades-team/forensic/snapshots/**": true
    },
    "editor.renderWhitespace": "boundary",
    "editor.minimap.enabled": false,
    "workbench.startupEditor": "none",
    "extensions.autoUpdate": true,
    "extensions.autoCheckUpdates": true,
    "terminal.integrated.env.linux": {
        "PURPLE_HOME": "/var/lib/pleiades-team",
        "FORENSIC_INTERVAL": "120"
    },
    "pleiades-team.watchFifo": true,
    "pleiades-team.autoReconnect": true,
    "pleiades-team.logLevel": "info"
}
SETTINGS
    log "workspace settings generated"

    # VS Code tasks for pleiades operations
    cat > "$VSCODE_TASKS" << 'TASKS'
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Purple: Status Dashboard",
            "type": "shell",
            "command": "systemctl list-units --type=service --state=running | grep -E 'pleiades|atlas|taygete|pleiades-nexus|maia'",
            "group": "none",
            "presentation": {"reveal": "always", "panel": "new"}
        },
        {
            "label": "Purple: View Forensic Score",
            "type": "shell",
            "command": "cat /run/pleiades/forensic_score 2>/dev/null || echo '0'",
            "group": "none",
            "presentation": {"reveal": "always", "panel": "new"}
        },
        {
            "label": "Purple: View Anomalies",
            "type": "shell",
            "command": "cat /run/pleiades/forensic_anomalies 2>/dev/null || echo 'none'",
            "group": "none",
            "presentation": {"reveal": "always", "panel": "new"}
        },
        {
            "label": "Purple: Run Chaos Monkey",
            "type": "shell",
            "command": "sudo /usr/local/bin/pleiades-chaos-monkey.sh --gentle",
            "group": "test",
            "presentation": {"reveal": "always", "panel": "new", "clear": true}
        },
        {
            "label": "Purple: Container Shell",
            "type": "shell",
            "command": "sudo nsenter -t $(cat /run/pleiades/container_pid 2>/dev/null || echo 1) -m -u -i -n -p",
            "group": "none",
            "presentation": {"reveal": "always", "panel": "new"}
        },
        {
            "label": "Purple: View Heartbeat Status",
            "type": "shell",
            "command": "cat /run/pleiades-gentoo-heartbeat/status 2>/dev/null || echo 'heartbeat not running'",
            "group": "none",
            "presentation": {"reveal": "always", "panel": "new"}
        },
        {
            "label": "Purple: Tail All Logs",
            "type": "shell",
            "command": "journalctl -u pleiades-*-omniversal.service -u pleiades-forensic-scanner.service -u pleiades-adaptive-builder.service -u maia.service -f --no-pager -n 50 2>/dev/null | tail -100",
            "group": "none",
            "presentation": {"reveal": "always", "panel": "new", "clear": false}
        }
    ]
}
TASKS
    log "workspace tasks generated"
}

# ─── VS Code Launch / Status ──────────────────────────────────────────────────
check_vscode() {
    if [[ -x "$VSCODE_BIN" ]]; then
        local version
        version=$("$VSCODE_BIN" --version 2>/dev/null | head -1)
        echo "VSCODE_AVAILABLE|version=${version}"
        return 0
    fi
    echo "VSCODE_UNAVAILABLE"
    return 1
}

launch_workspace() {
    log "launching VS Code workspace at $WORKSPACE_DIR"
    # Launch VS Code in background — it detaches itself
    "$VSCODE_BIN" "$WORKSPACE_DIR" --new-window 2>/dev/null &
    echo $! > "$BRIDGE_DIR/vscode.pid"
    log "VS Code launched (PID $(cat "$BRIDGE_DIR/vscode.pid"))"
}

# ─── Event Forwarding (Event Log → VS Code Notification) ──────────────────────
forward_events() {
    if [[ ! -p "$EVENT_FIFO" ]]; then
        rm -f "$EVENT_FIFO"
        mkfifo "$EVENT_FIFO"
    fi
    
    # Periodically dump recent events to a file VS Code can watch
    local SOURCE_LOG="${PLEIADES_RUN_DIR}/pleiades-nexus_fifo"
    local WATCH_FILE="$BRIDGE_DIR/recent_events.log"
    local OFFSET_FILE="$BRIDGE_DIR/pleiades-nexus.offset"
    local offset=0 size new_data
    if [[ -f "$OFFSET_FILE" ]]; then
        offset="$(cat "$OFFSET_FILE" 2>/dev/null || echo 0)"
        [[ "$offset" =~ ^[0-9]+$ ]] || offset=0
    fi
    
    while true; do
        if [[ -f "$SOURCE_LOG" ]]; then
            size=$(stat -c%s "$SOURCE_LOG" 2>/dev/null || echo 0)
            [[ "$size" =~ ^[0-9]+$ ]] || size=0
            (( offset <= size )) || offset=0
            if (( size > offset )); then
                new_data=$(dd if="$SOURCE_LOG" bs=1 skip="$offset" 2>/dev/null || true)
                offset=$size
                printf '%s\n' "$offset" > "$OFFSET_FILE"
                if [[ -n "$new_data" ]]; then
                    while IFS= read -r line; do
                        [[ -n "$line" ]] && printf '%s %s\n' "$(date -u +%H:%M:%S)" "$line" >> "$WATCH_FILE"
                    done <<< "$new_data"
                    # Keep last 100 lines
                    tail -100 "$WATCH_FILE" > "${WATCH_FILE}.tmp" && mv "${WATCH_FILE}.tmp" "$WATCH_FILE"
                fi
            fi
        fi
        sleep 2
    done
}

# ─── Main ─────────────────────────────────────────────────────────────────────
main() {
    mkdir -p "$BRIDGE_DIR"
    
    case "${1:-status}" in
        status)
            check_vscode
            if [[ -f "$BRIDGE_DIR/vscode.pid" ]]; then
                local pid
                pid=$(cat "$BRIDGE_DIR/vscode.pid")
                if kill -0 "$pid" 2>/dev/null; then
                    echo "bridge: connected (PID $pid)"
                else
                    echo "bridge: disconnected (stale PID $pid)"
                fi
            fi
            ;;
        setup)
            generate_workspace
            log "workspace ready at $WORKSPACE_DIR"
            echo "Workspace ready. Open in VS Code Insiders:"
            echo "  $VSCODE_BIN $WORKSPACE_DIR"
            ;;
        launch)
            generate_workspace
            launch_workspace
            ;;
        forward)
            forward_events
            ;;
        *)
            echo "Usage: $0 {status|setup|launch|forward}"
            exit 1
            ;;
    esac
}

main "$@"
