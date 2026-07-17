#!/usr/bin/env bash
# maia-overseer.sh — Maia, the silent overseer (lean, no polling loop).
#   init        establish the current node trust root
#   checkpoint  signed liveness, bridge ingestion and transactional Nexus seal
#   seal        seal queued events immediately
set -uo pipefail

source /usr/local/lib/pleiades/pleiades-common.sh
PLEIADES_LOG_TAG=maia
AGENT=maia

NEXDIR=/var/lib/maia/nexus
LEDGER="$NEXDIR/ledger"
GENESIS=0000000000000000000000000000000000000000000000000000000000000000
WIN_SPOOL=/host/win/spool/windows-events.log
WIN_CURSOR="$NEXDIR/windows.cursor"
NET_SPOOL=/host/win/spool/netwatch.log
NET_CURSOR="$NEXDIR/netwatch.cursor"

requeue_from_line() {
    local work="$1" start_line="$2" spool="$PLEIADES_NEXUS_SPOOL"
    (
        exec 7>>"${spool}.lock" || exit 1
        flock 7 || exit 1
        tail -n "+${start_line}" "$work" >> "$spool"
    )
}

# Delete an inflight file only after its remaining records are safely back in
# the queue. When requeue fails, preserve the file for the next recovery pass.
requeue_and_clear() {
    local work="$1" start_line="$2" reason="$3"
    if requeue_from_line "$work" "$start_line"; then
        rm -f "$work"
        log_warn "nexus: $reason; current and remaining events requeued"
        return 0
    fi
    log_err "nexus: $reason and requeue failed; evidence preserved at $work"
    return 1
}

recover_stale_inflight() {
    local spool="$PLEIADES_NEXUS_SPOOL" stale found=0
    shopt -s nullglob
    for stale in "${spool}.inflight."*; do
        found=1
        (
            exec 7>>"${spool}.lock" || exit 1
            flock 7 || exit 1
            cat "$stale" >> "$spool"
            rm -f "$stale"
        ) || {
            shopt -u nullglob
            log_err "nexus: failed to recover stale inflight file $stale"
            return 1
        }
    done
    shopt -u nullglob
    [[ "$found" -eq 0 ]] || log_warn "nexus: recovered stale inflight events; duplicates are possible and event IDs must be deduplicated downstream"
}

# Claim the current queue atomically. The claimed file remains beside the spool,
# so a process crash leaves an obvious recoverable inflight artifact.
claim_spool() {
    local work="$1" spool="$PLEIADES_NEXUS_SPOOL"
    (
        exec 7>>"${spool}.lock" || exit 1
        flock 7 || exit 1
        [[ -s "$spool" ]] || exit 3
        mv "$spool" "$work"
        : > "$spool"
    )
}

nexus_seal() {
    mkdir -p "$NEXDIR" "$(dirname "$PLEIADES_NEXUS_SPOOL")" || {
        log_err "nexus: cannot create ledger or spool directory"
        return 1
    }
    chmod 700 "$NEXDIR" || {
        log_err "nexus: cannot protect $NEXDIR"
        return 1
    }
    recover_stale_inflight || return 1

    local spool="$PLEIADES_NEXUS_SPOOL" work rc
    work="${spool}.inflight.$$.$RANDOM"
    claim_spool "$work"
    rc=$?
    [[ "$rc" -eq 3 ]] && return 0
    if [[ "$rc" -ne 0 ]]; then
        log_err "nexus: failed to claim queued events rc=$rc"
        return "$rc"
    fi

    local seq prev
    if [[ -s "$LEDGER" ]]; then
        seq="$(tail -1 "$LEDGER" | cut -d'|' -f1)"
        prev="$(tail -1 "$LEDGER" | cut -d'|' -f5)"
    else
        seq=0
        prev="$GENESIS"
    fi

    local n=0 line_no=0 ts eb64 input hash sig hf ev
    while IFS= read -r ev; do
        line_no=$((line_no + 1))
        [[ -z "$ev" ]] && continue
        seq=$((seq + 1))
        ts="$(date +%s)"
        eb64="$(printf '%s' "$ev" | openssl base64 -A)"
        input="${seq}|${ts}|${prev}|${eb64}"
        hash="$(printf '%s' "$input" | openssl dgst -sha256 | awk '{print $NF}')"
        hf="$(mktemp)" || {
            requeue_and_clear "$work" "$line_no" "temporary signature input creation failed" || :
            status_set "$AGENT" degraded "signature_input_failed" || :
            return 1
        }
        printf '%s' "$hash" > "$hf"
        if ! sig="$(maia-crypto sign "$hf")"; then
            rm -f "$hf"
            requeue_and_clear "$work" "$line_no" "ledger signing failed at seq=$seq" || :
            status_set "$AGENT" degraded "ledger_sign_failed" || :
            return 1
        fi
        rm -f "$hf"
        if ! printf '%s|%s|%s|%s|%s|%s\n' "$seq" "$ts" "$prev" "$eb64" "$hash" "$sig" >> "$LEDGER"; then
            requeue_and_clear "$work" "$line_no" "ledger append failed at seq=$seq" || :
            status_set "$AGENT" degraded "ledger_append_failed" || :
            return 1
        fi
        prev="$hash"
        n=$((n + 1))
    done < "$work"

    rm -f "$work"
    chmod 600 "$LEDGER" || {
        status_set "$AGENT" degraded "ledger_permissions_failed" || :
        log_err "nexus: unable to set ledger permissions"
        return 1
    }
    if command -v sync >/dev/null 2>&1 && ! sync -f "$LEDGER"; then
        log_warn "nexus: sync -f failed; ledger remains written but durability is not confirmed"
    fi
    [[ "$n" -gt 0 ]] && log_info "nexus: sealed $n event(s), head seq=$seq"
    return 0
}

windows_ingest() {
    [[ -r "$WIN_SPOOL" ]] || return 0
    local cur=0 total
    [[ -f "$WIN_CURSOR" ]] && cur="$(cat "$WIN_CURSOR" 2>/dev/null || echo 0)"
    total="$(wc -l < "$WIN_SPOOL" 2>/dev/null || echo 0)"
    [[ "$total" -le "$cur" ]] && return 0
    tail -n "+$((cur + 1))" "$WIN_SPOOL" | while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        nexus_emit windows_event "$line" || exit 1
    done || return 1
    echo "$total" > "$WIN_CURSOR"
    log_info "windows: ingested $((total - cur)) event(s) from bridge"
}

windows_net_ingest() {
    [[ -r "$NET_SPOOL" ]] || return 0
    local cur=0 total
    [[ -f "$NET_CURSOR" ]] && cur="$(cat "$NET_CURSOR" 2>/dev/null || echo 0)"
    total="$(wc -l < "$NET_SPOOL" 2>/dev/null || echo 0)"
    [[ "$total" -le "$cur" ]] && return 0
    tail -n "+$((cur + 1))" "$NET_SPOOL" | while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        nexus_emit net_event "$line" || exit 1
    done || return 1
    echo "$total" > "$NET_CURSOR"
    log_info "netwatch: ingested $((total - cur)) event(s) from bridge"
}

do_init() {
    log_info "Maia init — establishing trust root"
    if ! require maia-crypto init; then
        status_set "$AGENT" failed "keygen_failed" || :
        nexus_emit maia_failed reason=keygen || :
        exit 1
    fi
    local fp
    fp="$(maia-crypto fingerprint)"
    status_set "$AGENT" ok "" || exit 1
    nexus_emit maia_started "key=$fp" || exit 1
    log_info "trust root ready: key $fp"
}

do_checkpoint() {
    if ! require maia-crypto init; then
        status_set "$AGENT" failed "keygen_failed" || :
        exit 1
    fi
    local fp ts sig cp=/run/pleiades/maia.checkpoint
    fp="$(maia-crypto fingerprint)"
    ts="$(date +%s)"
    printf 'maia-alive:%s' "$ts" > "$cp"
    sig="$(maia-crypto sign "$cp")" || {
        status_set "$AGENT" degraded "sign_failed" || :
        nexus_emit maia_degraded reason=sign || :
        exit 1
    }
    status_set "$AGENT" ok "" || exit 1
    nexus_emit maia_checkpoint "key=$fp" "ts=$ts" "load=$(host_load)" "sig=${sig:0:16}" || exit 1
    windows_ingest || { status_set "$AGENT" degraded "windows_ingest_failed" || :; exit 1; }
    windows_net_ingest || { status_set "$AGENT" degraded "net_ingest_failed" || :; exit 1; }
    nexus_seal || exit 1
}

case "${1:-}" in
    init)       do_init ;;
    checkpoint) do_checkpoint ;;
    seal)       nexus_seal ;;
    *) echo "usage: maia-overseer.sh {init|checkpoint|seal}" >&2; exit 2 ;;
esac
