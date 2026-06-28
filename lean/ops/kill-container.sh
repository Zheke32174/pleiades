#!/bin/bash
# Hard-stop the container (simulate a crash) — kill init by pid-namespace.
HOSTNS=$(readlink /proc/1/ns/pid)
for p in $(pgrep -x systemd); do
  [ "$(readlink /proc/$p/ns/pid 2>/dev/null)" != "$HOSTNS" ] && { echo "killing container init $p"; kill -9 "$p" 2>/dev/null; }
done
tmux kill-server 2>/dev/null
pkill -9 systemd-nspawn 2>/dev/null
sleep 2
echo "after kill -> nspawn: $(pgrep -c systemd-nspawn 2>/dev/null || echo 0)"
