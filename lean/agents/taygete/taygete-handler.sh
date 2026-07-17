#!/usr/bin/env bash
# taygete-handler.sh — per-connection SSH honeypot handler.
# stdin/stdout are the remote TCP connection supplied by systemd socket
# activation. The handler has no key access and no host authority.
set -uo pipefail
source /usr/local/lib/pleiades/pleiades-common.sh
PLEIADES_LOG_TAG=taygete

PEER="${1:-unknown}"
endpoint="${PEER##*-}"
IP="${endpoint%:*}"
PORT="${endpoint##*:}"

printf 'SSH-2.0-OpenSSH_9.6p1 Ubuntu-3ubuntu13.5\r\n'

client=""
if ! IFS= read -r -t 5 client; then client=""; fi
client="$(printf '%s' "$client" | tr -cd '[:print:]' | tr ' ' '_' | cut -c1-120)"
[[ -n "$client" ]] || client=none

log_info "connection from $PEER client='$client'"
if ! nexus_emit hostile_recon "peer=$IP" "port=$PORT" "client=$client"; then
    log_err "evidence submission failed for connection from $PEER"
    exit 1
fi
