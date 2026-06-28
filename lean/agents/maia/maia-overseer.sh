#!/usr/bin/env bash
# maia-overseer.sh — Maia, the silent overseer (lean, NO polling loop).
#   init        once at boot (oneshot, RemainAfterExit) — establish trust root
#   checkpoint  by a slow jittered .timer — signed liveness + seal the Nexus
# No `while true; sleep` here. Cadence lives in the timer.
set -uo pipefail

source /usr/local/lib/pleiades/pleiades-common.sh
PLEIADES_LOG_TAG=maia
AGENT=maia

NEXDIR=/var/lib/maia/nexus
LEDGER="$NEXDIR/ledger"
GENESIS=0000000000000000000000000000000000000000000000000000000000000000
# Windows bridge: read-only spool from the always-on Windows side (AD/Security
# events). Mounted at /host/win by the container boot if C:\pleiades exists.
WIN_SPOOL=/host/win/spool/windows-events.log
WIN_CURSOR="$NEXDIR/windows.cursor"

# --- Nexus sealing: drain the spool into the hash-chained, signed ledger ----
nexus_seal() {
    mkdir -p "$NEXDIR"; chmod 700 "$NEXDIR" 2>/dev/null
    local spool="$PLEIADES_NEXUS_SPOOL"
    [ -s "$spool" ] || return 0

    # Atomically claim the queued events (hold the spool lock only briefly).
    local work; work="$(mktemp)"
    ( exec 7>>"${spool}.lock"; flock 7; cat "$spool" > "$work" 2>/dev/null; : > "$spool" )
    [ -s "$work" ] || { rm -f "$work"; return 0; }

    # Continue the chain from the ledger tail.
    local seq prev
    if [ -s "$LEDGER" ]; then
        seq="$(tail -1 "$LEDGER" | cut -d'|' -f1)"
        prev="$(tail -1 "$LEDGER" | cut -d'|' -f5)"
    else
        seq=0; prev="$GENESIS"
    fi

    local n=0 ts eb64 input hash sig hf
    while IFS= read -r ev; do
        [ -z "$ev" ] && continue
        seq=$((seq+1)); ts="$(date +%s)"
        eb64="$(printf '%s' "$ev" | openssl base64 -A)"
        input="${seq}|${ts}|${prev}|${eb64}"
        hash="$(printf '%s' "$input" | openssl dgst -sha256 | awk '{print $NF}')"
        hf="$(mktemp)"; printf '%s' "$hash" > "$hf"
        sig="$(maia-crypto sign "$hf")" || { rm -f "$hf"; log_err "nexus: sign failed at seq=$seq"; break; }
        rm -f "$hf"
        printf '%s|%s|%s|%s|%s|%s\n' "$seq" "$ts" "$prev" "$eb64" "$hash" "$sig" >> "$LEDGER"
        prev="$hash"; n=$((n+1))
    done < "$work"
    rm -f "$work"
    chmod 600 "$LEDGER" 2>/dev/null
    [ "$n" -gt 0 ] && log_info "nexus: sealed $n event(s), head seq=$seq"
    return 0
}

# --- Windows bridge ingest: pull new AD/Security events into the Nexus --------
windows_ingest() {
    [ -r "$WIN_SPOOL" ] || return 0          # bridge not mounted -> no-op
    local cur=0; [ -f "$WIN_CURSOR" ] && cur="$(cat "$WIN_CURSOR" 2>/dev/null || echo 0)"
    local total; total="$(wc -l < "$WIN_SPOOL" 2>/dev/null || echo 0)"
    [ "$total" -le "$cur" ] && return 0      # nothing new
    tail -n +"$((cur+1))" "$WIN_SPOOL" | while IFS= read -r line; do
        [ -z "$line" ] && continue
        nexus_emit windows_event "$line"
    done
    echo "$total" > "$WIN_CURSOR"
    log_info "windows: ingested $((total-cur)) event(s) from bridge"
}

do_init() {
    log_info "Maia init — establishing trust root"
    if ! require maia-crypto init; then
        status_set "$AGENT" failed "keygen_failed"
        nexus_emit maia_failed "reason=keygen"
        exit 1
    fi
    local fp; fp="$(maia-crypto fingerprint)"
    log_info "trust root ready: key $fp"
    status_set "$AGENT" ok ""
    nexus_emit maia_started "key=$fp"
}

do_checkpoint() {
    if ! require maia-crypto init; then
        status_set "$AGENT" failed "keygen_failed"; exit 1
    fi
    local fp ts sig cp=/run/pleiades/maia.checkpoint
    fp="$(maia-crypto fingerprint)"; ts="$(date +%s)"
    printf 'maia-alive:%s' "$ts" > "$cp"
    sig="$(maia-crypto sign "$cp")" || { status_set "$AGENT" degraded "sign_failed"; nexus_emit maia_degraded "reason=sign"; exit 1; }
    status_set "$AGENT" ok ""
    nexus_emit maia_checkpoint "key=$fp ts=$ts load=$(host_load) sig=${sig:0:16}"
    # Pull any new Windows/AD events from the bridge, then seal everything queued.
    windows_ingest
    nexus_seal
}

case "${1:-}" in
    init)       do_init ;;
    checkpoint) do_checkpoint ;;
    seal)       nexus_seal ;;
    *) echo "usage: maia-overseer.sh {init|checkpoint|seal}" >&2; exit 2 ;;
esac
