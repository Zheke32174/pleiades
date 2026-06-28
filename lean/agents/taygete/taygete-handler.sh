#!/usr/bin/env bash
# taygete-handler.sh — per-connection SSH honeypot handler (socket-activated).
# stdin/stdout ARE the attacker's TCP connection. One short-lived instance per
# connection, spawned by pleiades-taygete.socket (Accept=yes). No daemon, no
# polling loop. Has NO access to Maia's private key — it only emits events.
set -uo pipefail
source /usr/local/lib/pleiades/pleiades-common.sh
PLEIADES_LOG_TAG=taygete

PEER="${1:-unknown}"          # %i = SEQ-ID-LOCALADDR:PORT-REMOTEADDR:PORT
endpoint="${PEER##*-}"        # last dash-segment is the remote addr:port
IP="${endpoint%:*}"
PORT="${endpoint##*:}"

# Low-interaction SSH banner. stdout is the connection.
printf 'SSH-2.0-OpenSSH_9.6p1 Ubuntu-3ubuntu13.5\r\n'

# Capture the client's identification string. A timeout here is NORMAL (a
# scanner may send nothing) — handled explicitly, not masked.
client=""
if ! IFS= read -r -t 5 client; then client=""; fi
client="$(printf '%s' "$client" | tr -cd '[:print:]' | tr ' ' '_' | cut -c1-120)"
[ -z "$client" ] && client="none"

log_info "connection from $PEER client='$client'"
nexus_emit hostile_recon peer="$IP" port="$PORT" client="$client"
exit 0
