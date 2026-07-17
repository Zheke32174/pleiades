#!/usr/bin/env bash
# celaeno-watch.sh — event-driven watchdog reporting.
# systemd owns supervision; Celaeno observes and records failures.
set -uo pipefail
source /usr/local/lib/pleiades/pleiades-common.sh
PLEIADES_LOG_TAG=celaeno
AGENT=celaeno

UNITS=(pleiades-maia.service pleiades-maia-checkpoint.timer pleiades-taygete.socket)

do_alert() {
    local unit="${1:-unknown}" res nr
    res="$(systemctl show -p Result --value "$unit" 2>/dev/null || echo unknown)"
    nr="$(systemctl show -p NRestarts --value "$unit" 2>/dev/null || echo 0)"
    log_err "swarm unit FAILED: $unit (result=$res nrestarts=$nr)"
    status_set "$AGENT" degraded "failed:$unit" || exit 1
    nexus_emit swarm_alert "unit=$unit" "result=$res" "nrestarts=$nr" || exit 1
}

do_survey() {
    local bad=0 summary="" u a nr
    for u in "${UNITS[@]}"; do
        a="$(systemctl is-active "$u" 2>/dev/null || echo unknown)"
        nr="$(systemctl show -p NRestarts --value "$u" 2>/dev/null || echo 0)"
        summary+="${u}=${a}/r${nr} "
        case "$a" in
            active|activating|listening|waiting) ;;
            *) bad=$((bad + 1)) ;;
        esac
    done

    if [[ "$bad" -eq 0 ]]; then
        status_set "$AGENT" ok "" || exit 1
    else
        status_set "$AGENT" degraded "${bad}_unit_down" || exit 1
    fi
    nexus_emit swarm_health "bad=$bad" "$summary" || exit 1
    echo "celaeno: ${summary}(bad=$bad)"
}

case "${1:-survey}" in
    alert)  shift; do_alert "$@" ;;
    survey) do_survey ;;
    *) echo "usage: celaeno-watch.sh {survey|alert <unit>}" >&2; exit 2 ;;
esac
