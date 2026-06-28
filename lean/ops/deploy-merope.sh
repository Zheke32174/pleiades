#!/bin/bash
# Deploy Merope and verify snapshot -> verify -> double-gated restore.
set -uo pipefail
ROOT=/workspaces/gentoo/root.x86_64; SRC=/mnt/c/pleiades-build; DEST="$ROOT/opt/pleiades-build"

echo "=== staging ==="
rm -rf "$DEST"; mkdir -p "$DEST"; cp -r "$SRC"/. "$DEST"/
find "$DEST" -type f -exec sed -i 's/\r$//' {} +
find "$DEST/agents" -type f -name '*.sh' -exec chmod +x {} +
chmod +x "$DEST/build.sh" "$DEST/agents/maia/maia-crypto" "$DEST/agents/nexus/nexus-verify"

HOSTNS=$(readlink /proc/1/ns/pid); CPID=""
for p in $(pgrep -x systemd); do [ "$(readlink /proc/$p/ns/pid 2>/dev/null)" != "$HOSTNS" ] && CPID=$p; done
[ -z "$CPID" ] && { echo CONTAINER_DOWN; exit 1; }
echo "container pid $CPID"

echo "=== build + enable snapshot timer ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash /opt/pleiades-build/build.sh || { echo BUILD_FAILED; exit 1; }
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc 'systemctl enable --now pleiades-merope.timer'

echo "=== snapshot + verify ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
systemctl start pleiades-merope.service; sleep 1
ls -1 /var/lib/maia/snapshots/maia-*.enc 2>/dev/null | sed "s|.*/|  snapshot: |"
SNAP=$(ls -1t /var/lib/maia/snapshots/maia-*.enc | head -1)
merope-rebirth.sh verify "$SNAP" | sed "s/^/  /"
'

echo "=== restore is double-gated (signature + owner guard) ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
SNAP=$(ls -1t /var/lib/maia/snapshots/maia-*.enc | head -1); L=/var/lib/maia/nexus/ledger
echo -n "  no-guard restore: "; merope-rebirth.sh restore "$SNAP" 2>&1 | tail -1
echo -n "  corrupt ledger:   "; awk -F"|" "NR==1{\$4=\$4 \"X\"} {print}" OFS="|" "$L" > "$L.t" && mv "$L.t" "$L"; nexus-verify | tail -1
touch /run/pleiades/REBIRTH_OK
echo -n "  guarded restore:  "; merope-rebirth.sh restore "$SNAP" 2>&1 | tail -1
echo -n "  after restore:    "; nexus-verify | tail -1
'

echo "=== seal + show merope/rebirth events ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc 'systemctl start pleiades-maia-checkpoint.service; sleep 1; nexus-verify --show 2>/dev/null | grep -E "snapshot_|rebirth_|nexus-verify:" | tail -5'

echo "=== timers + health ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
echo "  pleiades timers: $(systemctl list-timers --no-pager | grep -c pleiades)"
echo "  failed units: $(systemctl list-units --state=failed --no-legend | wc -l)"'
echo "=== done ==="
