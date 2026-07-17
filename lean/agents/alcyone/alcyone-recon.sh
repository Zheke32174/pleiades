#!/usr/bin/env bash
# alcyone-recon.sh — Alcyone, recon/posture (lean rebuild).
#
# Alcyone observes the network namespace visible to its container and emits a
# posture event. It does not browse host filesystem bridges, write host state,
# or perform countermeasures. Host telemetry must arrive through a collector.
set -uo pipefail
source /usr/local/lib/pleiades/pleiades-common.sh
PLEIADES_LOG_TAG=alcyone
AGENT=alcyone

# Transitional desired-state list. This will be replaced by signed service,
# executable and socket manifests rather than port-only identity.
EXPECTED="2222 2323 8088 80 53 5355 3306 33060"

do_recon() {
    local ports listeners established anomaly=""
    ports=$(ss -H -tln 2>/dev/null | awk '{print $4}' | sed 's/.*://' | sort -un | tr '\n' ' ')
    listeners=$(printf '%s' "$ports" | wc -w)
    established=$(ss -H -tn state established 2>/dev/null | wc -l)

    for p in $ports; do
        case " $EXPECTED " in
            *" $p "*) ;;
            *) anomaly="${anomaly:+$anomaly,}$p" ;;
        esac
    done

    if [[ -n "$anomaly" ]]; then
        status_set "$AGENT" degraded "unexpected_listeners:$anomaly" || exit 1
        nexus_emit recon_anomaly \
            "unexpected_ports=$anomaly" \
            "listeners=$listeners" \
            "established=$established" \
            "host_telemetry=collector_required" || exit 1
    else
        status_set "$AGENT" ok "" || exit 1
        nexus_emit recon_posture \
            "listeners=$listeners" \
            "established=$established" \
            "ports=${ports// /,}" \
            "host_telemetry=collector_required" || exit 1
    fi
    echo "alcyone: listeners=$listeners established=$established anomaly=${anomaly:-none}"
}

case "${1:-recon}" in
    recon) do_recon ;;
    *) echo "usage: alcyone-recon.sh recon" >&2; exit 2 ;;
esac
