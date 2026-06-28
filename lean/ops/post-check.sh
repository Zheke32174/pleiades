#!/bin/bash
HOSTNS=$(readlink /proc/1/ns/pid); CPID=""
for p in $(pgrep -x systemd); do [ "$(readlink /proc/$p/ns/pid 2>/dev/null)" != "$HOSTNS" ] && CPID=$p; done
[ -z "$CPID" ] && { echo "CONTAINER DOWN"; exit 1; }
echo "container pid $CPID"
nsenter -t "$CPID" -m -u -i -n -p -- bash -lc '
echo "  system: $(systemctl is-system-running 2>/dev/null)"
echo "  maia:   $(systemctl is-active pleiades-maia.service)"
echo "  bridge: $([ -r /host/win/spool/windows-events.log ] && echo OK || echo MISSING)"
echo "  ledger: $(nexus-verify 2>/dev/null | tail -1)"
'
