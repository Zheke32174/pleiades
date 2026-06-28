#!/bin/bash
# Stage the clean build tree into the running container, build, and verify Maia.
# Handles the transition from the old looping daemon to the oneshot+timer design.
set -uo pipefail
ROOT=/workspaces/gentoo/root.x86_64
SRC=/mnt/c/pleiades-build
DEST="$ROOT/opt/pleiades-build"

echo "=== staging build tree into container rootfs ==="
rm -rf "$DEST"; mkdir -p "$DEST"
cp -r "$SRC"/. "$DEST"/
find "$DEST" -type f -exec sed -i 's/\r$//' {} +
chmod +x "$DEST/build.sh" "$DEST/agents/maia/maia-crypto" "$DEST/agents/maia/maia-overseer.sh"

HOSTNS=$(readlink /proc/1/ns/pid); CPID=""
for p in $(pgrep -x systemd); do [ "$(readlink /proc/$p/ns/pid 2>/dev/null)" != "$HOSTNS" ] && CPID=$p; done
[ -z "$CPID" ] && { echo "CONTAINER DOWN"; exit 1; }
echo "container pid $CPID"

echo "=== transition: stop old looping daemon, remove stale files ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
systemctl stop pleiades-maia.service 2>/dev/null || true
rm -f /usr/local/sbin/maia-daemon.sh
'

echo "=== build (inside container) ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash /opt/pleiades-build/build.sh || { echo "BUILD FAILED"; exit 1; }

echo "=== enable oneshot init + checkpoint timer ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
systemctl enable --now pleiades-maia.service pleiades-maia-checkpoint.timer
'

echo "=== verify: no running maia process (no polling loop) ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
echo "maia.service: $(systemctl is-active pleiades-maia.service) / sub=$(systemctl show -p SubState --value pleiades-maia.service)"
procs=$(pgrep -af "maia-overseer|maia-daemon" | grep -v checkpoint || true)
[ -z "$procs" ] && echo "OK: no persistent maia loop process" || { echo "FOUND persistent loop:"; echo "$procs"; }
'

echo "=== verify: trigger ONE checkpoint manually + show cadence ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
systemctl start pleiades-maia-checkpoint.service
sleep 1
echo "--- status json ---"; cat /run/pleiades/state/maia.json 2>/dev/null
echo "--- timer cadence ---"; systemctl list-timers pleiades-maia-checkpoint.timer --no-pager 2>/dev/null | sed "s/^/    /"
echo "--- recent nexus ---"; journalctl -t pleiades-nexus --no-pager -n 3 2>/dev/null | sed "s/^/    /"
'
echo "=== done ==="
