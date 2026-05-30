#!/usr/bin/env bash
# Purple-team session-start status. Prints situational awareness at the top
# of every Claude session in this repo. Keep FAST and read-only.
set -u

echo "── purple-team ──"

# Gentoo nspawn state
if PID=$(pgrep -x systemd-nspawn 2>/dev/null | head -1) && [ -n "$PID" ]; then
  ETIME=$(ps -p "$PID" -o etime= 2>/dev/null | tr -d ' ')
  echo "  nspawn:        UP  pid=$PID  uptime=$ETIME"
else
  echo "  nspawn:        DOWN  (run sudo systemd-nspawn ... or heartbeat script)"
fi

# Host bridges status
STATUS_FILE=/run/purple-gentoo-heartbeat/status
if [ -f "$STATUS_FILE" ]; then
  BRIDGES=$(grep -o 'bridge_[a-z_]*=[a-z]*' "$STATUS_FILE" 2>/dev/null | tr '\n' '  ')
  LAST=$(grep 'last_result=' "$STATUS_FILE" 2>/dev/null | cut -d= -f2)
  echo "  bridges:       ${BRIDGES:-(no bridge data)}  last=${LAST:-unknown}"
else
  echo "  bridges:       status file not found (heartbeat not running?)"
fi

# Inside-container service check (only if nspawn is up)
if [ -n "$PID" ]; then
  FAILED=$(nsenter -t "$PID" -m -u -i -n -p -- \
    systemctl --failed --no-legend 2>/dev/null | wc -l)
  ACTIVE=$(nsenter -t "$PID" -m -u -i -n -p -- \
    systemctl --state=active --no-legend --type=service 2>/dev/null | wc -l)
  echo "  services:      $ACTIVE active, $FAILED failed"

  # Threat mode
  ZOD=$(nsenter -t "$PID" -m -u -i -n -p -- \
    cat /run/purple/zod_mode 2>/dev/null)
  echo "  threat mode:   ${ZOD:-UNKNOWN}"
fi

# Disk on /workspaces
DISK=$(df -h /workspaces 2>/dev/null | awk 'NR==2 {printf "%s used of %s (%s)", $3, $2, $5}')
[ -n "$DISK" ] && echo "  /workspaces:   $DISK"

# Swap pressure
if swapon --show=NAME --noheadings 2>/dev/null | grep -q .; then
  read -r SWAP_TOTAL SWAP_USED <<<"$(free -h | awk '/^Swap:/ {print $2, $3}')"
  echo "  swap:          $SWAP_USED used / $SWAP_TOTAL total"
fi

echo
