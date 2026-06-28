#!/bin/bash
# Deploy Alcyone (read-only recon) and verify posture sealing + read-only enforcement.
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

echo "=== build + enable recon timer ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash /opt/pleiades-build/build.sh || { echo BUILD_FAILED; exit 1; }
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc 'systemctl enable --now pleiades-alcyone.timer'

echo "=== run one recon + show result ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
systemctl start pleiades-alcyone.service; sleep 1
echo "--- listeners in container ---"; ss -tlnH | awk "{print \$4}" | sort -u | sed "s/^/  /"
echo "--- alcyone status ---"; cat /run/pleiades/state/alcyone.json 2>/dev/null; echo
echo "--- alcyone journal ---"; journalctl -t alcyone --no-pager -n 2 | sed "s/^/  /"
'

echo "=== read-only enforcement: a host write must FAIL under the sandbox ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
systemd-run --quiet --pipe --property=ProtectSystem=strict --property=ReadWritePaths=/run/pleiades \
  bash -c "echo x > /var/lib/maia/INTRUSION 2>&1 && echo WROTE || echo BLOCKED"'

echo "=== seal + show recon event in ledger ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc 'systemctl start pleiades-maia-checkpoint.service; sleep 1; nexus-verify --show 2>/dev/null | grep -E "recon_|nexus-verify:" | tail -4'

echo "=== timers + health ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
echo "  pleiades timers: $(systemctl list-timers --no-pager | grep -c pleiades)"
echo "  failed units: $(systemctl list-units --state=failed --no-legend | wc -l)"'
echo "=== done ==="
