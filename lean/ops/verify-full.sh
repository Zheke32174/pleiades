#!/usr/bin/env bash
# Comprehensive in-container verification of the Pleiades lean stack.
set -uo pipefail

HOSTNS=$(readlink /proc/1/ns/pid)
CPID=""
for p in $(pgrep -x systemd); do
    [[ "$(readlink /proc/$p/ns/pid 2>/dev/null)" != "$HOSTNS" ]] && CPID=$p
done
[[ -n "$CPID" ]] || { echo "CONTAINER DOWN"; exit 1; }

nsenter -t "$CPID" -m -u -i -n -p -- bash -s <<'EOF'
set -uo pipefail
PASS=0
FAIL=0
ok(){ PASS=$((PASS+1)); echo "  [PASS] $1"; }
no(){ FAIL=$((FAIL+1)); echo "  [FAIL] $1"; }
chk(){ if eval "$2" >/dev/null 2>&1; then ok "$1"; else no "$1"; fi; }

echo "== container / systemd =="
chk "systemd running/degraded" '[ "$(systemctl is-system-running)" = running ] || [ "$(systemctl is-system-running)" = degraded ]'
chk "zero failed units" '[ "$(systemctl list-units --state=failed --no-legend | wc -l)" -eq 0 ]'
chk "pleiades.slice installed" 'systemctl cat pleiades.slice'

echo "== agent binaries installed =="
for b in maia-crypto:/usr/local/bin/maia-crypto maia:/usr/local/sbin/maia-overseer.sh nexus:/usr/local/bin/nexus-verify taygete:/usr/local/sbin/taygete-handler.sh celaeno:/usr/local/sbin/celaeno-watch.sh electra:/usr/local/sbin/electra-decoy.sh alcyone:/usr/local/sbin/alcyone-recon.sh merope:/usr/local/sbin/merope-rebirth.sh sterope:/usr/local/sbin/sterope-score.sh; do
  chk "binary ${b%%:*}" "[ -x ${b#*:} ]"
done

echo "== sockets / services active =="
chk "maia.service active"            '[ "$(systemctl is-active pleiades-maia.service)" = active ]'
chk "taygete.socket active"          '[ "$(systemctl is-active pleiades-taygete.socket)" = active ]'
chk "electra-http.socket active"     '[ "$(systemctl is-active pleiades-electra-http.socket)" = active ]'
chk "electra-telnet.socket active"   '[ "$(systemctl is-active pleiades-electra-telnet.socket)" = active ]'

echo "== cadence: exactly 4 slow timers =="
chk "4 pleiades timers" '[ "$(systemctl list-timers --all --no-pager | grep -c pleiades)" -eq 4 ]'

echo "== Maia trust root =="
printf trustme > /tmp/_v
SIG=$(maia-crypto sign /tmp/_v)
chk "sign + verify round-trip" 'maia-crypto verify /tmp/_v "$SIG"'
printf evil > /tmp/_v2
chk "tampered input rejected" '! maia-crypto verify /tmp/_v2 "$SIG"'
rm -f /tmp/_v /tmp/_v2

echo "== Nexus transaction and ledger =="
chk "checkpoint and seal complete" 'systemctl start pleiades-maia-checkpoint.service'
chk "nexus-verify valid non-empty ledger" 'nexus-verify'
chk "sealed event carries event_id" 'nexus-verify --show | grep -q "event_id="'
chk "no abandoned inflight queue" '! compgen -G "/run/pleiades/nexus.spool.inflight.*" >/dev/null'

echo "== live sensor probes =="
( exec 3<>/dev/tcp/127.0.0.1/2222; read -t 3 b <&3; printf 'SSH-2.0-verify\r\n' >&3; exec 3>&- ) && ok "taygete :2222 honeypot answered" || no "taygete :2222"
( exec 3<>/dev/tcp/127.0.0.1/8088; read -t 3 b <&3; printf 'GET / HTTP/1.0\r\n\r\n' >&3; exec 3>&- ) && ok "electra :8088 decoy answered" || no "electra :8088"
( exec 3<>/dev/tcp/127.0.0.1/2323; read -t 3 b <&3; printf 'root\r\n' >&3; exec 3>&- ) && ok "electra :2323 decoy answered" || no "electra :2323"

echo "== sandbox enforcement =="
chk "host write blocked by sandbox" '! systemd-run -q --pipe -p ProtectSystem=strict -p ReadWritePaths=/run/pleiades bash -c "echo x > /var/lib/maia/_INTRUSION"'
chk "Taygete has empty capability bounding set" 'systemctl show pleiades-taygete@.service -p CapabilityBoundingSet --value | grep -qx ""'

echo "== Celaeno OnFailure watchdog =="
systemctl reset-failed pleiades-vtest 2>/dev/null || :
systemd-run -q --unit=pleiades-vtest -p "OnFailure=pleiades-celaeno-alert@pleiades-vtest.service" /bin/false 2>/dev/null || :
sleep 1
chk "celaeno alerted on unit failure" 'grep -q "\"status\":\"degraded\"" /run/pleiades/state/celaeno.json'
systemctl reset-failed pleiades-vtest 2>/dev/null || :

echo "== Merope snapshot + gated restore =="
systemctl start pleiades-merope.service
sleep 1
SNAP=$(ls -1t /var/lib/maia/snapshots/maia-*.enc 2>/dev/null | head -1)
chk "snapshot created"             '[ -n "$SNAP" ]'
chk "snapshot signature verifies"  'merope-rebirth.sh verify "$SNAP"'
chk "restore refused without guard" '! merope-rebirth.sh restore "$SNAP"'

echo "== Sterope threat scoring =="
systemctl start pleiades-sterope.service
sleep 1
chk "threat_mode written"  '[ -s /run/pleiades/threat_mode ]'
chk "sterope status ok"    'grep -q "\"status\":\"ok\"" /run/pleiades/state/sterope.json'

echo "== final seal and verification =="
chk "final checkpoint succeeds" 'systemctl start pleiades-maia-checkpoint.service'
chk "ledger valid after full exercise" 'nexus-verify'

echo
echo "===================================="
echo "   IN-CONTAINER RESULT: PASS=$PASS  FAIL=$FAIL"
echo "===================================="
[[ "$FAIL" -eq 0 ]] || exit 1
EOF
