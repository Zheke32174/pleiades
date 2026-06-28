#!/usr/bin/env bash
# celaeno-watch.sh — Celaeno, the watchdog (lean rebuild).
# The old Celaeno had a `while true; systemctl restart` storm. That logic is
# DELETED: systemd owns supervision (Restart=on-failure + StartLimitBurst).
# Celaeno only OBSERVES and REPORTS — it never restarts anything.
#   alert <unit>   event-driven, fired by a failing unit's OnFailure= handler
#   survey         on-demand health summary (NOT driven by any timer)
set -uo pipefail
source /usr/local/lib/pleiades/pleiades-common.sh
PLEIADES_LOG_TAG=celaeno
AGENT=celaeno

UNITS=(pleiades-maia.service pleiades-maia-checkpoint.timer pleiades-taygete.socket)

do_alert() {                # alert <failed-unit>
    local unit="${1:-unknown}"
    local res nr
    res="$(systemctl show -p Result --value "$unit" 2>/dev/null || echo unknown)"
    nr="$(systemctl show -p NRestarts --value "$unit" 2>/dev/null || echo 0)"
    log_err "swarm unit FAILED: $unit (result=$res nrestarts=$nr)"
    nexus_emit swarm_alert unit="$unit" result="$res" nrestarts="$nr"
    status_set "$AGENT" degraded "failed:$unit"
}

do_survey() {               # on-demand; no timer drives this
    local bad=0 summary=""
    for u in "${UNITS[@]}"; do
        local a nr
        a="$(systemctl is-active "$u" 2>/dev/null || echo unknown)"
        nr="$(systemctl show -p NRestarts --value "$u" 2>/dev/null || echo 0)"
        summary+="${u}=${a}/r${nr} "
        case "$a" in active|activating|listening|waiting) ;; *) bad=$((bad+1)) ;; esac
    done
    if [ "$bad" -eq 0 ]; then status_set "$AGENT" ok ""; else status_set "$AGENT" degraded "${bad}_unit_down"; fi
    nexus_emit swarm_health bad="$bad" "$summary"
    echo "celaeno: ${summary}(bad=$bad)"
}

case "${1:-survey}" in
    alert)  shift; do_alert "$@" ;;
    survey) do_survey ;;
    *) echo "usage: celaeno-watch.sh {survey|alert <unit>}" >&2; exit 2 ;;
esac
