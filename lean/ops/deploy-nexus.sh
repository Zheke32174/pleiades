#!/bin/bash
# Deploy the Nexus ledger (sealing in Maia) and verify integrity + tamper detection.
set -uo pipefail
ROOT=/workspaces/gentoo/root.x86_64
SRC=/mnt/c/pleiades-build
DEST="$ROOT/opt/pleiades-build"

echo "=== staging ==="
rm -rf "$DEST"; mkdir -p "$DEST"; cp -r "$SRC"/. "$DEST"/
find "$DEST" -type f -exec sed -i 's/\r$//' {} +
chmod +x "$DEST/build.sh" "$DEST/agents/maia/maia-crypto" "$DEST/agents/maia/maia-overseer.sh" "$DEST/agents/nexus/nexus-verify"

HOSTNS=$(readlink /proc/1/ns/pid); CPID=""
for p in $(pgrep -x systemd); do [ "$(readlink /proc/$p/ns/pid 2>/dev/null)" != "$HOSTNS" ] && CPID=$p; done
[ -z "$CPID" ] && { echo CONTAINER_DOWN; exit 1; }
echo "container pid $CPID"

echo "=== build + reload + refresh maia ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash /opt/pleiades-build/build.sh || { echo BUILD_FAILED; exit 1; }
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc 'systemctl restart pleiades-maia.service'

echo "=== emit events, seal via checkpoint, verify the ledger ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
set -e
source /usr/local/lib/pleiades/pleiades-common.sh
nexus_emit test_event source=deploy detail=alpha
nexus_emit test_event source=deploy detail=bravo
systemctl start pleiades-maia-checkpoint.service; sleep 1
systemctl start pleiades-maia-checkpoint.service; sleep 1
echo "--- ledger tail (truncated) ---"; tail -2 /var/lib/maia/nexus/ledger | cut -c1-88
echo "--- nexus-verify --show ---"; nexus-verify --show
'

echo "=== tamper test: alter one record, expect TAMPER, then restore ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
L=/var/lib/maia/nexus/ledger
cp "$L" "$L.bak"
awk -F"|" "NR==1{\$4=\$4 \"X\"} {print}" OFS="|" "$L" > "$L.t" && mv "$L.t" "$L"
echo -n "tampered ledger -> "; nexus-verify || true
mv "$L.bak" "$L"
echo -n "restored ledger -> "; nexus-verify
'
echo "=== done ==="
