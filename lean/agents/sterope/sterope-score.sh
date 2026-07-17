#!/usr/bin/env bash
# sterope-score.sh — observe-only defensive threat scoring.
#
# This transitional scorer consumes signed event records and emits a bounded
# posture summary. It does not execute containment or modify host state.
set -uo pipefail
source /usr/local/lib/pleiades/pleiades-common.sh
PLEIADES_LOG_TAG=sterope
AGENT=sterope

LEDGER=/var/lib/maia/nexus/ledger
WINDOW="${STEROPE_WINDOW:-3600}"

do_score() {
    local now cutoff score=0 fl=0 dh=0 ra=0 sa=0 ne=0 ev
    now=$(date +%s)
    cutoff=$((now - WINDOW))

    if [[ ! -f "$LEDGER" ]]; then
        status_set "$AGENT" ok "" || exit 1
        nexus_emit threat_score score=0 mode=NORMAL note=no_ledger || exit 1
        echo "sterope: no ledger"
        return 0
    fi

    while IFS='|' read -r seq ts prev eb64 hash sig; do
        [[ -n "${ts:-}" ]] || continue
        [[ "$ts" -ge "$cutoff" ]] || continue
        ev=$(printf '%s' "$eb64" | openssl base64 -d -A 2>/dev/null) || continue
        case "$ev" in
            *failed_logon*)       fl=$((fl + 1)); score=$((score + 3)) ;;
            *hostile_recon*)      score=$((score + 4)) ;;
            *decoy_hit*)          dh=$((dh + 1)); score=$((score + 5)) ;;
            *recon_anomaly*)      ra=$((ra + 1)); score=$((score + 6)) ;;
            *swarm_alert*)        sa=$((sa + 1)); score=$((score + 4)) ;;
            *gateway_mac_change*) ne=$((ne + 1)); score=$((score + 10)) ;;
            *arp_conflict*)       ne=$((ne + 1)); score=$((score + 8)) ;;
            *dns_change*)         ne=$((ne + 1)); score=$((score + 5)) ;;
        esac
    done < "$LEDGER"

    local mode=NORMAL
    if [[ "$score" -ge 30 ]]; then
        mode=HIGH
    elif [[ "$score" -ge 10 ]]; then
        mode=ELEVATED
    fi

    if ! printf '%s\n' "$mode" > /run/pleiades/threat_mode; then
        status_set "$AGENT" degraded "threat_mode_write_failed" || :
        log_err "unable to write threat mode"
        return 1
    fi

    status_set "$AGENT" ok "" || exit 1
    nexus_emit threat_score \
        "score=$score" \
        "mode=$mode" \
        "failed_logon=$fl" \
        "decoy=$dh" \
        "anomaly=$ra" \
        "alert=$sa" \
        "net=$ne" \
        "window=${WINDOW}s" || exit 1
    echo "sterope: score=$score mode=$mode (fl=$fl decoy=$dh anomaly=$ra alert=$sa net=$ne)"
}

case "${1:-score}" in
    score) do_score ;;
    *) echo "usage: sterope-score.sh score" >&2; exit 2 ;;
esac
