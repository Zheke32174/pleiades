#!/bin/bash
# Deploy Sterope (defensive threat scoring) and verify scoring from real signals.
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

echo "=== build + enable scoring timer ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash /opt/pleiades-build/build.sh || { echo BUILD_FAILED; exit 1; }
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc 'systemctl enable --now pleiades-sterope.timer'

echo "=== run scoring (uses real recent ledger signals) ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
systemctl start pleiades-sterope.service; sleep 1
echo "  threat_mode file: $(cat /run/pleiades/threat_mode 2>/dev/null)"
echo "  sterope status:   $(cat /run/pleiades/state/sterope.json 2>/dev/null)"
'

echo "=== seal + show threat_score event ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc 'systemctl start pleiades-maia-checkpoint.service; sleep 1; nexus-verify --show 2>/dev/null | grep -E "threat_score|nexus-verify:" | tail -3'

echo "=== final: all timers + health ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
echo "  pleiades timers: $(systemctl list-timers --no-pager | grep -c pleiades)"
echo "  failed units: $(systemctl list-units --state=failed --no-legend | wc -l)"
echo "  installed agents: $(ls /usr/local/sbin/*-*.sh /usr/local/bin/maia-crypto 2>/dev/null | wc -l)"'
echo "=== done ==="
