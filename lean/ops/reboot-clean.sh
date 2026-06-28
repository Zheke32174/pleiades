#!/bin/bash
# Properly tear down the (possibly orphaned) container, then boot fresh with the
# Windows bridge bind. Kills container processes by pid-namespace, not just nspawn.
HOSTNS=$(readlink /proc/1/ns/pid)

echo "=== killing container init(s) by pid-namespace ==="
for p in $(pgrep -x systemd); do
  ns=$(readlink /proc/$p/ns/pid 2>/dev/null)
  [ -n "$ns" ] && [ "$ns" != "$HOSTNS" ] && { echo "  kill container systemd $p"; kill -9 "$p" 2>/dev/null; }
done
tmux kill-server 2>/dev/null
pkill -9 systemd-nspawn 2>/dev/null
sleep 2

echo "=== sweeping leftover orphan processes in foreign pid-namespaces ==="
for p in $(ls /proc 2>/dev/null | grep -E '^[0-9]+$'); do
  ns=$(readlink /proc/$p/ns/pid 2>/dev/null)
  [ -n "$ns" ] && [ "$ns" != "$HOSTNS" ] && kill -9 "$p" 2>/dev/null
done
sleep 1
left=$(for p in $(pgrep -x systemd); do [ "$(readlink /proc/$p/ns/pid 2>/dev/null)" != "$HOSTNS" ] && echo "$p"; done | tr '\n' ' ')
echo "  remaining foreign systemd: '${left:-none}'  nspawn: $(pgrep -c systemd-nspawn 2>/dev/null || echo 0)"

echo "=== booting fresh with bind ==="
bash /mnt/c/pleiades-analysis/boot-tmux.sh

echo "=== verify bridge + nspawn args ==="
pgrep -af systemd-nspawn | sed 's/^/  /'
HOSTNS=$(readlink /proc/1/ns/pid); CPID=""
for p in $(pgrep -x systemd); do [ "$(readlink /proc/$p/ns/pid 2>/dev/null)" != "$HOSTNS" ] && CPID=$p; done
echo "  container pid: $CPID"
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '[ -r /host/win/spool/windows-events.log ] && echo "  BRIDGE_OK ($(wc -l < /host/win/spool/windows-events.log) lines)" || echo "  BRIDGE_FAIL"'
