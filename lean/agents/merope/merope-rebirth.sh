#!/usr/bin/env bash
# merope-rebirth.sh — Merope, snapshot/restore (lean rebuild).
# The old Merope fired restores off flaky bgp/thermal heuristics. This one is
# safe: snapshots are encrypted (owner escrow key) + Maia-signed; RESTORE is
# double-gated (valid signature AND an explicit owner guard flag) — never
# triggered by a heuristic, never loops.
#   snapshot          encrypted+signed snapshot of /var/lib/maia (keys+ledger)
#   verify   <f.enc>  check a snapshot's Maia signature
#   restore  <f.enc>  signature-gated + guard-gated restore
set -uo pipefail
source /usr/local/lib/pleiades/pleiades-common.sh
PLEIADES_LOG_TAG=merope
AGENT=merope

MAIADIR=/var/lib/maia
SNAPDIR="$MAIADIR/snapshots"
ESCROW="$MAIADIR/escrow.key"     # owner secret: BACK THIS UP SEPARATELY (loss = no restore)
GUARD=/run/pleiades/REBIRTH_OK   # owner must create this to permit a restore

ensure_escrow() {
    if [ ! -f "$ESCROW" ]; then
        ( umask 077; openssl rand -hex 32 > "$ESCROW" )
        log_warn "generated escrow key $ESCROW — OWNER MUST back this up separately (loss = no restore)"
    fi
}

do_snapshot() {
    ensure_escrow; mkdir -p "$SNAPDIR"
    local ts tar enc sig hash size
    ts=$(date +%s); tar="$SNAPDIR/maia-$ts.tar.gz"; enc="$SNAPDIR/maia-$ts.enc"; sig="$SNAPDIR/maia-$ts.sig"
    tar czf "$tar" -C "$MAIADIR" --exclude=snapshots --exclude=escrow.key . 2>/dev/null
    if ! openssl enc -aes-256-cbc -pbkdf2 -salt -in "$tar" -out "$enc" -pass file:"$ESCROW"; then
        rm -f "$tar" "$enc"; status_set "$AGENT" degraded "encrypt_failed"; nexus_emit snapshot_failed "reason=encrypt"; return 1
    fi
    rm -f "$tar"
    hash=$(openssl dgst -sha256 "$enc" | awk '{print $NF}')
    printf '%s' "$hash" > "$SNAPDIR/.h"; maia-crypto sign "$SNAPDIR/.h" > "$sig"; rm -f "$SNAPDIR/.h"
    ls -1t "$SNAPDIR"/maia-*.enc 2>/dev/null | tail -n +6 | while read -r old; do rm -f "$old" "${old%.enc}.sig"; done
    size=$(wc -c < "$enc")
    status_set "$AGENT" ok ""
    nexus_emit snapshot_created "file=$(basename "$enc") bytes=$size sha256=${hash:0:16}"
    echo "merope: snapshot $(basename "$enc") ($size bytes)"
}

do_verify() {
    local enc="${1:?usage: verify <file.enc>}" sig="${1%.enc}.sig"
    [ -f "$enc" ] && [ -f "$sig" ] || { echo "missing $enc or its .sig"; return 1; }
    local hash; hash=$(openssl dgst -sha256 "$enc" | awk '{print $NF}')
    printf '%s' "$hash" > /tmp/.mh
    if maia-crypto verify /tmp/.mh "$(cat "$sig")"; then rm -f /tmp/.mh; echo "VERIFY_OK $(basename "$enc")"; return 0
    else rm -f /tmp/.mh; echo "VERIFY_FAIL $(basename "$enc")"; return 1; fi
}

do_restore() {
    local enc="${1:?usage: restore <file.enc>}"
    if [ ! -f "$GUARD" ]; then
        log_err "restore REFUSED: owner guard $GUARD absent"
        nexus_emit rebirth_refused "file=$(basename "$enc") reason=no_guard"; return 1
    fi
    if ! do_verify "$enc" >/dev/null; then
        nexus_emit rebirth_refused "file=$(basename "$enc") reason=bad_signature"; return 1
    fi
    ensure_escrow
    local tmp; tmp=$(mktemp -d)
    if ! openssl enc -d -aes-256-cbc -pbkdf2 -in "$enc" -out "$tmp/r.tar.gz" -pass file:"$ESCROW"; then
        rm -rf "$tmp"; nexus_emit rebirth_refused "reason=decrypt_failed"; return 1
    fi
    tar xzf "$tmp/r.tar.gz" -C "$MAIADIR"
    rm -rf "$tmp"; rm -f "$GUARD"
    nexus_emit rebirth_done "file=$(basename "$enc")"
    echo "merope: restored from $(basename "$enc")"
}

case "${1:-snapshot}" in
    snapshot) do_snapshot ;;
    verify)   shift; do_verify "$@" ;;
    restore)  shift; do_restore "$@" ;;
    *) echo "usage: merope-rebirth.sh {snapshot|verify <f.enc>|restore <f.enc>}" >&2; exit 2 ;;
esac
