#!/usr/bin/env bash
# electra-decoy.sh <service> <peer> — socket-activated deception handler.
# Each connection is short-lived, resource-bounded, and limited to event
# submission. Electra has no key access and no host authority.
set -uo pipefail
source /usr/local/lib/pleiades/pleiades-common.sh
PLEIADES_LOG_TAG=electra

SVC="${1:-generic}"
PEER="${2:-unknown}"
endpoint="${PEER##*-}"
IP="${endpoint%:*}"
PORT="${endpoint##*:}"

case "$SVC" in
    telnet) printf '\r\nUbuntu 22.04.5 LTS\r\nlogin: ' ;;
    http)   printf 'HTTP/1.1 401 Unauthorized\r\nServer: nginx/1.24.0\r\nWWW-Authenticate: Basic realm="Admin"\r\nContent-Length: 0\r\n\r\n' ;;
    redis)  printf '%s\r\n' '-NOAUTH Authentication required.' ;;
    *)      printf 'OK\r\n' ;;
esac

data=""
if ! IFS= read -r -t 5 data; then data=""; fi
data="$(printf '%s' "$data" | tr -cd '[:print:]' | tr ' ' '_' | cut -c1-120)"
[[ -n "$data" ]] || data=none

log_info "decoy $SVC hit from $PEER data='$data'"
if ! nexus_emit decoy_hit "service=$SVC" "peer=$IP" "port=$PORT" "data=$data"; then
    log_err "evidence submission failed for $SVC connection from $PEER"
    exit 1
fi
