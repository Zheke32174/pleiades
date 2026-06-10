#!/usr/bin/env bash
# ryz-compliance: f2d6b64d shell
# wsl-bounty-scanner.sh — daily WSL-layer security sweep (host side)
# Runs at 02:00 via pleiades-bounty-scanner.timer.
# Checks for unexpected listening ports, new SUID binaries, suspicious cron entries,
# and large rogue processes. Writes report to /home/fixxia/lamp/logs/bounty-YYYYMMDD.log.
set -uo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

REPORT_DIR="/home/fixxia/lamp/logs"
TODAY=$(date +%Y%m%d)
REPORT="$REPORT_DIR/bounty-${TODAY}.log"
BASELINE_PORTS="/home/fixxia/lamp/state/bounty-baseline-ports.txt"
BASELINE_SUID="/home/fixxia/lamp/state/bounty-baseline-suid.txt"
ISSUES=0

mkdir -p "$REPORT_DIR" "/home/fixxia/lamp/state"

log()  { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$REPORT"; }
warn() { echo "[$(date '+%H:%M:%S')] WARN: $*" | tee -a "$REPORT"; ISSUES=$((ISSUES+1)); }
ok()   { echo "[$(date '+%H:%M:%S')] OK:   $*" | tee -a "$REPORT"; }

log "=== WSL bounty scan $(date '+%Y-%m-%d %H:%M:%S') ==="

# ── 1. Unexpected listening TCP/UDP ports ────────────────────────────────────
KNOWN_PORTS="22|25|53|80|323|389|443|631|2222|2223|2224|3306|5353|5355|8000|8001|8005|8080|8083|8443|8787|8923|9090|14321|14322|18080|19022|33060|37700"
LISTENING=$(ss -tlnpu 2>/dev/null | awk 'NR>1 {print $5}' | grep -oE '[0-9]+$' | sort -un)
NEW_PORTS=""
for port in $LISTENING; do
  if ! echo "$port" | grep -qE "^($KNOWN_PORTS)$"; then
    NEW_PORTS="$NEW_PORTS $port"
  fi
done
if [[ -n "$NEW_PORTS" ]]; then
  warn "unexpected listening ports:$NEW_PORTS"
  ss -tlnpu 2>/dev/null | grep -E "$(echo "$NEW_PORTS" | tr ' ' '|')" >> "$REPORT" || true
else
  ok "listening ports: all within known set"
fi

# ── 2. SUID binary delta ─────────────────────────────────────────────────────
CURRENT_SUID=$(find /usr/bin /usr/sbin /bin /sbin -perm -4000 -type f 2>/dev/null | sort)
if [[ ! -f "$BASELINE_SUID" ]]; then
  echo "$CURRENT_SUID" > "$BASELINE_SUID"
  ok "SUID baseline created (first run)"
else
  NEW_SUID=$(comm -23 <(echo "$CURRENT_SUID") "$BASELINE_SUID" 2>/dev/null)
  if [[ -n "$NEW_SUID" ]]; then
    warn "new SUID binaries since baseline: $NEW_SUID"
  else
    ok "SUID binaries: no changes"
  fi
fi

# ── 3. Cron anomaly scan ─────────────────────────────────────────────────────
ALL_CRONS=$(crontab -l 2>/dev/null; cat /etc/cron.d/* 2>/dev/null; ls /etc/cron.{hourly,daily,weekly,monthly}/ 2>/dev/null)
# Flag base64/curl/wget piped to bash in crons — classic dropper pattern
# Exclude known-good patterns: /tmp/revenue-daily.log (revenue-hub cron output redirect)
SUSPICIOUS=$(echo "$ALL_CRONS" | grep -E 'base64|curl.*\|.*bash|wget.*\|.*bash|/tmp/[a-zA-Z0-9]{6,}' | grep -vE '/tmp/revenue-daily' || true)
if [[ -n "$SUSPICIOUS" ]]; then
  warn "suspicious cron pattern detected: $SUSPICIOUS"
else
  ok "cron entries: no suspicious patterns"
fi

# ── 4. Rogue large processes (>800MB RSS, not in known-good set) ─────────────
KNOWN_PROCS="mysqld|apache2|node|claude|gemini|anubis|systemd|sshd|python"
while IFS= read -r line; do
  PID=$(echo "$line" | awk '{print $1}')
  RSS_MB=$(echo "$line" | awk '{printf "%d", $2/1024}')
  CMD=$(echo "$line" | awk '{print $3}')
  if ! echo "$CMD" | grep -qE "$KNOWN_PROCS"; then
    warn "unrecognized large process: PID=$PID RSS=${RSS_MB}MB CMD=$CMD"
  fi
done < <(ps aux --sort=-%mem | awk 'NR>1 && $6>819200 {print $2, $6, $11}' 2>/dev/null)

# ── 5. /tmp suspicious files ─────────────────────────────────────────────────
# Exclude known-good dirs: ryz_batch_test_* (RYZ native binary test staging)
TMP_EXEC=$(find /tmp /var/tmp -maxdepth 2 -type f -executable 2>/dev/null \
    | grep -vE '/tmp/ryz_batch_test_|/tmp/ryz_native_test_|/tmp/ryz-batch-audit' \
    | head -20)
if [[ -n "$TMP_EXEC" ]]; then
  warn "executable files in /tmp: $TMP_EXEC"
else
  ok "/tmp: no unexpected executables"
fi

# ── 6. WSL host memory sanity ────────────────────────────────────────────────
MEM_AVAIL=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
if [[ $MEM_AVAIL -lt 300 ]]; then
  warn "WSL memory critically low: ${MEM_AVAIL}MB available"
else
  ok "WSL memory: ${MEM_AVAIL}MB available"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
log "=== scan complete: $ISSUES issue(s) ==="

# Keep only last 14 daily reports
find "$REPORT_DIR" -name "bounty-*.log" -mtime +14 -delete 2>/dev/null || true

# Always exit 0 — the service succeeds when it runs; findings are in the log.
# Exit 1 here causes systemd to show the unit as "failed" even on clean runs,
# polluting the failed-units view. Security findings are communicated via log.
exit 0
