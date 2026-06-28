#!/bin/bash
# Deploy Electra (multi-port decoy farm) and verify hits seal into the ledger.
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

echo "=== build + enable decoy sockets ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash /opt/pleiades-build/build.sh || { echo BUILD_FAILED; exit 1; }
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc 'systemctl enable --now pleiades-electra-http.socket pleiades-electra-telnet.socket'

echo "=== verify listening + probe both decoys (pure bash /dev/tcp) ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
for s in pleiades-electra-http.socket pleiades-electra-telnet.socket; do echo "  $s = $(systemctl is-active $s)"; done
ss -tlnp 2>/dev/null | grep -E ":8088 |:2323 " | sed "s/^/  /"
probe() { # port  payload
  if exec 3<>/dev/tcp/127.0.0.1/$1; then
    IFS= read -r -t 3 banner <&3 || true
    printf "%s\r\n" "$2" >&3
    echo "  port $1 banner: ${banner:0:40}"
    exec 3>&- 3<&-
  else echo "  port $1 connect failed"; fi
}
probe 8088 "GET /admin HTTP/1.0"
sleep 0.3
probe 2323 "root"
sleep 0.3
'

echo "=== telemetry + seal into signed ledger ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
echo "--- electra journal ---"; journalctl -t electra --no-pager -n 3 2>/dev/null | sed "s/^/  /"
systemctl start pleiades-maia-checkpoint.service; sleep 1
echo "--- nexus-verify --show (tail) ---"; nexus-verify --show 2>/dev/null | tail -5
'

echo "=== event-driven + cadence checks ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
live=$(systemctl list-units "pleiades-electra-*@*" --state=active --no-legend 2>/dev/null | wc -l)
[ "$live" -eq 0 ] && echo "  OK: no decoy handlers active between connections" || echo "  active handlers: $live"
echo "  pleiades timers: $(systemctl list-timers --no-pager | grep -c pleiades)"
echo "  failed units: $(systemctl list-units --state=failed --no-legend | wc -l)"
'
echo "=== done ==="
