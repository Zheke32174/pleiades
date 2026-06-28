#!/usr/bin/env bash
# electra-decoy.sh <service> <peer> — per-connection decoy handler (socket-activated).
# Electra = deception. Stands up believable decoy services on commonly-scanned
# ports; any contact is hostile (nothing legit talks to these) and is sealed
# into the Nexus. No daemon, no polling, no host access, no key access.
set -uo pipefail
source /usr/local/lib/pleiades/pleiades-common.sh
PLEIADES_LOG_TAG=electra

SVC="${1:-generic}"
PEER="${2:-unknown}"          # %i = SEQ-ID-LOCAL:PORT-REMOTE:PORT
endpoint="${PEER##*-}"; IP="${endpoint%:*}"; PORT="${endpoint##*:}"

# Believable banner per decoy type (stdout is the connection).
case "$SVC" in
    telnet) printf '\r\nUbuntu 22.04.5 LTS\r\nlogin: ' ;;
    http)   printf 'HTTP/1.1 401 Unauthorized\r\nServer: nginx/1.24.0\r\nWWW-Authenticate: Basic realm="Admin"\r\nContent-Length: 0\r\n\r\n' ;;
    redis)  printf '-NOAUTH Authentication required.\r\n' ;;
    *)      printf 'OK\r\n' ;;
esac

# Capture the first line of attacker input (timeout is expected, not an error).
data=""
if ! IFS= read -r -t 5 data; then data=""; fi
data="$(printf '%s' "$data" | tr -cd '[:print:]' | tr ' ' '_' | cut -c1-120)"
[ -z "$data" ] && data="none"

log_info "decoy $SVC hit from $PEER data='$data'"
nexus_emit decoy_hit service="$SVC" peer="$IP" port="$PORT" data="$data"
exit 0
