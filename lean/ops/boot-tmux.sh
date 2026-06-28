#!/bin/bash
set -uo pipefail
ROOT=/workspaces/gentoo/root.x86_64
command -v tmux >/dev/null || { echo "installing tmux..."; DEBIAN_FRONTEND=noninteractive apt-get install -y tmux >/dev/null 2>&1; }
HOSTNS=$(readlink /proc/1/ns/pid)

teardown() {
  for p in $(pgrep -x systemd); do
    [ "$(readlink /proc/$p/ns/pid 2>/dev/null)" != "$HOSTNS" ] && kill -9 "$p" 2>/dev/null
  done
  tmux kill-server 2>/dev/null
  pkill -9 systemd-nspawn 2>/dev/null; sleep 2
  for p in $(ls /proc 2>/dev/null | grep -E '^[0-9]+$'); do
    ns=$(readlink /proc/$p/ns/pid 2>/dev/null)
    [ -n "$ns" ] && [ "$ns" != "$HOSTNS" ] && kill -9 "$p" 2>/dev/null
  done
  sleep 1
}

find_cpid() { CPID=""; for p in $(pgrep -x systemd); do [ "$(readlink /proc/$p/ns/pid 2>/dev/null)" != "$HOSTNS" ] && { CPID=$p; return; }; done; }

BIND=""
[ -d /mnt/c/pleiades ] && BIND="--bind-ro=/mnt/c/pleiades:/host/win"

CPID=""
for attempt in 1 2 3; do
  teardown
  mountpoint -q /run/systemd/nspawn 2>/dev/null || { mkdir -p /run/systemd/nspawn; mount -t tmpfs tmpfs /run/systemd/nspawn 2>/dev/null || true; }
  echo "boot attempt $attempt (tmux session 'gentoo')..."
  tmux new-session -d -s gentoo "systemd-nspawn --boot -D '$ROOT' --register=no --resolv-conf=copy-host --hostname=pleiades $BIND"
  for i in $(seq 1 50); do find_cpid; [ -n "$CPID" ] && break; sleep 0.5; done
  [ -n "$CPID" ] && break
  echo "  attempt $attempt failed; retrying..."
done

if [ -z "$CPID" ]; then
  echo "FAIL: container systemd not found after 3 attempts"
  tmux capture-pane -t gentoo -p 2>/dev/null | tail -25
  exit 1
fi

echo "=== CONTAINER UP — container systemd PID $CPID (boot attempt $attempt) ==="
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
  . /etc/os-release 2>/dev/null
  echo "  OS:      $PRETTY_NAME"
  echo "  state:   $(systemctl is-system-running 2>/dev/null)"
  echo "  running: $(systemctl list-units --type=service --state=running --no-legend 2>/dev/null | wc -l) services"
  echo "  failed:  $(systemctl list-units --state=failed --no-legend 2>/dev/null | wc -l)"
'
