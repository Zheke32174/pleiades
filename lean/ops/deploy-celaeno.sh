#!/bin/bash
# Deploy Celaeno (event-driven watchdog). Verify it alerts on failure via
# systemd OnFailure (no polling, no restart loop, no new timer).
set -uo pipefail
ROOT=/workspaces/gentoo/root.x86_64; SRC=/mnt/c/pleiades-build; DEST="$ROOT/opt/pleiades-build"

echo "=== staging ==="
rm -rf "$DEST"; mkdir -p "$DEST"; cp -r "$SRC"/. "$DEST"/
find "$DEST" -type f -exec sed -i 's/\r$//' {} +
chmod +x "$DEST/build.sh" "$DEST"/agents/maia/maia-crypto "$DEST"/agents/maia/maia-overseer.sh \
         "$DEST"/agents/nexus/nexus-verify "$DEST"/agents/taygete/taygete-handler.sh \
         "$DEST"/agents/celaeno/celaeno-watch.sh

HOSTNS=$(readlink /proc/1/ns/pid); CPID=""
for p in $(pgrep -x systemd); do [ "$(readlink /proc/$p/ns/pid 2>/dev/null)" != "$HOSTNS" ] && CPID=$p; done
[ -z "$CPID" ] && { echo CONTAINER_DOWN; exit 1; }
echo "container pid $CPID"

echo "=== build + reload maia (picks up OnFailure) ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash /opt/pleiades-build/build.sh || { echo BUILD_FAILED; exit 1; }
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc 'systemctl restart pleiades-maia.service'

echo "=== test: force a unit failure -> Celaeno alerts via OnFailure (event-driven) ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
systemctl reset-failed pleiades-fault-test 2>/dev/null || true
systemd-run --quiet --unit=pleiades-fault-test \
  --property="OnFailure=pleiades-celaeno-alert@pleiades-fault-test.service" /bin/false || true
sleep 1
echo "--- celaeno journal ---"; journalctl -t celaeno --no-pager -n 2 2>/dev/null | sed "s/^/  /"
echo "--- celaeno status ---"; cat /run/pleiades/state/celaeno.json 2>/dev/null; echo
systemctl reset-failed pleiades-fault-test 2>/dev/null || true
'

echo "=== on-demand survey + seal into signed ledger ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
celaeno-watch.sh survey
systemctl start pleiades-maia-checkpoint.service; sleep 1
echo "--- nexus-verify --show (tail) ---"; nexus-verify --show 2>/dev/null | tail -5
'

echo "=== cadence: confirm NO new timer (only the slow maia checkpoint) ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
systemctl list-timers --no-pager | grep -c pleiades | sed "s/^/  pleiades timers: /"
systemctl list-timers --no-pager | sed "s/^/  /"
nf=$(systemctl list-units --state=failed --no-legend | wc -l); echo "  failed units: $nf"
'
echo "=== done ==="
