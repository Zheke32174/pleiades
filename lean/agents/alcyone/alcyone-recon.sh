#!/usr/bin/env bash
# alcyone-recon.sh — Alcyone, recon/posture (lean rebuild).
# The old Alcyone wrote host paths + ran active countermeasures while claiming to
# be read-only. This one is READ-ONLY, enforced by the systemd sandbox (it can
# write only /run/pleiades). It snapshots listeners + connections, flags drift,
# and emits a signed posture record. No host writes, no countermeasures, no key.
set -uo pipefail
source /usr/local/lib/pleiades/pleiades-common.sh
PLEIADES_LOG_TAG=alcyone
AGENT=alcyone

# The container shares the host network namespace, so recon sees the DC's listeners
# too (useful — a host backdoor would show). Baseline = our sensors (2222/2323/8088)
# + the DC's known-legit services (80 web, 3306/33060 MySQL, 53 DNS, 5355 LLMNR).
# Any listener NOT in this set is drift worth a signed anomaly record.
EXPECTED="2222 2323 8088 80 53 5355 3306 33060"

do_recon() {
    local ports listeners established anomaly="" bridge="absent"
    ports=$(ss -H -tln 2>/dev/null | awk '{print $4}' | sed 's/.*://' | sort -un | tr '\n' ' ')
    listeners=$(printf '%s' "$ports" | wc -w)
    established=$(ss -H -tn state established 2>/dev/null | wc -l)
    for p in $ports; do
        case " $EXPECTED " in *" $p "*) ;; *) anomaly="${anomaly:+$anomaly,}$p" ;; esac
    done
    [ -r /host/win/spool/windows-events.log ] && bridge="ok"

    if [ -n "$anomaly" ]; then
        status_set "$AGENT" degraded "unexpected_listeners:$anomaly"
        nexus_emit recon_anomaly "unexpected_ports=$anomaly listeners=$listeners established=$established bridge=$bridge"
    else
        status_set "$AGENT" ok ""
        nexus_emit recon_posture "listeners=$listeners established=$established ports=${ports// /,} bridge=$bridge"
    fi
    echo "alcyone: listeners=$listeners established=$established anomaly=${anomaly:-none} bridge=$bridge"
}

case "${1:-recon}" in
    recon) do_recon ;;
    *) echo "usage: alcyone-recon.sh recon" >&2; exit 2 ;;
esac
