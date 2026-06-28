#!/usr/bin/env bash
# sterope-score.sh — Sterope, threat scoring (lean rebuild).
# The old Sterope wrote TTY-flood/"thrall" retaliation payloads to attacker IPs.
# That offensive code is GONE. This one only OBSERVES: it tallies recent signed
# events into a weighted threat score + posture mode and reports. No actions
# against anyone, no host writes beyond /run/pleiades, no key access.
set -uo pipefail
source /usr/local/lib/pleiades/pleiades-common.sh
PLEIADES_LOG_TAG=sterope
AGENT=sterope

LEDGER=/var/lib/maia/nexus/ledger
WINDOW="${STEROPE_WINDOW:-3600}"      # score events from the last hour

do_score() {
    local now cutoff score=0 fl=0 dh=0 ra=0 sa=0 ev
    now=$(date +%s); cutoff=$((now - WINDOW))
    [ -f "$LEDGER" ] || { status_set "$AGENT" ok ""; nexus_emit threat_score "score=0 mode=NORMAL note=no_ledger"; echo "sterope: no ledger"; return 0; }
    while IFS='|' read -r seq ts prev eb64 hash sig; do
        [ -z "${ts:-}" ] && continue
        [ "$ts" -lt "$cutoff" ] && continue
        ev=$(printf '%s' "$eb64" | openssl base64 -d -A 2>/dev/null)
        case "$ev" in
            *failed_logon*)  fl=$((fl+1)); score=$((score+3)) ;;
            *hostile_recon*) score=$((score+4)) ;;
            *decoy_hit*)     dh=$((dh+1)); score=$((score+5)) ;;
            *recon_anomaly*) ra=$((ra+1)); score=$((score+6)) ;;
            *swarm_alert*)   sa=$((sa+1)); score=$((score+4)) ;;
        esac
    done < "$LEDGER"

    local mode=NORMAL
    if   [ "$score" -ge 30 ]; then mode=HIGH
    elif [ "$score" -ge 10 ]; then mode=ELEVATED; fi
    echo "$mode" > /run/pleiades/threat_mode 2>/dev/null

    status_set "$AGENT" ok ""
    nexus_emit threat_score "score=$score mode=$mode failed_logon=$fl decoy=$dh anomaly=$ra alert=$sa window=${WINDOW}s"
    echo "sterope: score=$score mode=$mode (fl=$fl decoy=$dh anomaly=$ra alert=$sa)"
}

case "${1:-score}" in
    score) do_score ;;
    *) echo "usage: sterope-score.sh score" >&2; exit 2 ;;
esac
