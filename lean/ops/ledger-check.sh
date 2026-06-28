#!/bin/bash
# Seal pending events, then report how many ledger records match $1 (default: any).
HOSTNS=$(readlink /proc/1/ns/pid); CPID=""
for p in $(pgrep -x systemd); do [ "$(readlink /proc/$p/ns/pid 2>/dev/null)" != "$HOSTNS" ] && CPID=$p; done
[ -z "$CPID" ] && { echo "DOWN"; exit 1; }
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc "systemctl start pleiades-maia-checkpoint.service; sleep 1; nexus-verify --show 2>/dev/null | grep -c \"${1:-.}\""
