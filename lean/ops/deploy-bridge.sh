#!/bin/bash
# Build the Windows-bridge ingest into Maia and verify AD events seal into the ledger.
# Assumes the container was (re)booted with --bind-ro=/mnt/c/pleiades:/host/win.
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

echo "=== bridge mount check ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
if [ -r /host/win/spool/windows-events.log ]; then
  echo "OK: bridge readable — $(wc -l < /host/win/spool/windows-events.log) event line(s) waiting"
else echo "!! bridge NOT readable at /host/win/spool — check the bind"; fi'

echo "=== build + restart maia + checkpoint (ingest + seal) ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash /opt/pleiades-build/build.sh || { echo BUILD_FAILED; exit 1; }
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc 'systemctl restart pleiades-maia.service; systemctl start pleiades-maia-checkpoint.service; sleep 1'

echo "=== nexus: AD/Windows events now signed into the ledger ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
nexus-verify --show 2>/dev/null | grep -E "windows_event|nexus-verify:" | tail -8'
echo "=== done ==="
