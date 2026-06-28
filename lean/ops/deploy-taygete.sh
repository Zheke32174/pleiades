#!/bin/bash
# Deploy Taygete (socket-activated SSH honeypot) and verify end-to-end:
# listen -> attacker probe -> telemetry -> sealed Nexus record. No daemon.
set -uo pipefail
ROOT=/workspaces/gentoo/root.x86_64
SRC=/mnt/c/pleiades-build
DEST="$ROOT/opt/pleiades-build"

echo "=== staging ==="
rm -rf "$DEST"; mkdir -p "$DEST"; cp -r "$SRC"/. "$DEST"/
find "$DEST" -type f -exec sed -i 's/\r$//' {} +
chmod +x "$DEST/build.sh" "$DEST/agents/maia/maia-crypto" "$DEST/agents/maia/maia-overseer.sh" \
         "$DEST/agents/nexus/nexus-verify" "$DEST/agents/taygete/taygete-handler.sh"

HOSTNS=$(readlink /proc/1/ns/pid); CPID=""
for p in $(pgrep -x systemd); do [ "$(readlink /proc/$p/ns/pid 2>/dev/null)" != "$HOSTNS" ] && CPID=$p; done
[ -z "$CPID" ] && { echo CONTAINER_DOWN; exit 1; }
echo "container pid $CPID"

echo "=== build + enable honeypot socket ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash /opt/pleiades-build/build.sh || { echo BUILD_FAILED; exit 1; }
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc 'systemctl restart pleiades-maia.service; systemctl enable --now pleiades-taygete.socket'

echo "=== verify listening + simulate two attacker probes (pure bash /dev/tcp) ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
echo "socket: $(systemctl is-active pleiades-taygete.socket)"
ss -tlnp 2>/dev/null | grep ":2222 " | sed "s/^/  /" || echo "  (ss unavailable)"
for probe in "SSH-2.0-libssh-scanner" "SSH-2.0-Go-evilbot"; do
  if exec 3<>/dev/tcp/127.0.0.1/2222; then
    IFS= read -r -t 3 banner <&3 || true
    printf "%s\r\n" "$probe" >&3
    echo "  probe=$probe  got_banner=${banner:0:32}"
    exec 3>&- 3<&-
  else echo "  connect failed"; fi
  sleep 0.4
done
'

echo "=== telemetry + seal into the signed ledger ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
echo "--- taygete journal ---"; journalctl -t taygete --no-pager -n 4 2>/dev/null | sed "s/^/  /"
systemctl start pleiades-maia-checkpoint.service; sleep 1
echo "--- nexus-verify --show (tail) ---"; nexus-verify --show 2>/dev/null | tail -6
'

echo "=== confirm event-driven (no persistent honeypot process) ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
live=$(systemctl list-units "pleiades-taygete@*" --state=active --no-legend 2>/dev/null | wc -l)
[ "$live" -eq 0 ] && echo "OK: no handler instances active between connections" || echo "active handlers: $live"
nf=$(systemctl list-units --state=failed --no-legend | wc -l); echo "failed units: $nf"
'
echo "=== done ==="
