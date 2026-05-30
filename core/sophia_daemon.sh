#!/bin/bash
SOPHIA_DIR="/var/lib/.sophia"
SOCKET="/run/sophia.sock"
mkdir -p "$SOPHIA_DIR/logs"

dispatch_cmd() {
    local cmd="$1"
    echo "$(date -u): $cmd" >> "$SOPHIA_DIR/logs/events.log"
    case "$cmd" in
        RESURRECTION_NEEDED)
            pgrep -f resurrection_hivemind >/dev/null 2>&1 || \
                /usr/local/sbin/install-resurrection-omniversal.sh &
            ;;
        IMPLOSION_TRIGGERED)
            pgrep -f imploder >/dev/null 2>&1 || \
                /usr/local/sbin/install-ouroboros-omniversal.sh &
            ;;
    esac
}

while true; do
    rm -f "$SOCKET"
    cmd=$(nc -lU "$SOCKET" 2>/dev/null) || { sleep 1; continue; }
    [[ -n "$cmd" ]] && dispatch_cmd "$cmd"
done
