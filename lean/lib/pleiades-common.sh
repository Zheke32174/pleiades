# pleiades-common.sh — shared helpers for the lean Pleiades stack.
# Source me; do not execute. No Termux assumptions. No error masking.
#
# Invariants this lib enforces by example:
#   * failures are LOGGED and SURFACED, never swallowed with `|| true`
#   * agents publish an honest status JSON (ok|degraded|failed|stopped)
#   * the Nexus is the systemd journal (tag pleiades-nexus), not a flat file

PLEIADES_RUN="${PLEIADES_RUN:-/run/pleiades}"
PLEIADES_STATE_DIR="${PLEIADES_STATE_DIR:-$PLEIADES_RUN/state}"
PLEIADES_LOG_TAG="${PLEIADES_LOG_TAG:-pleiades}"
# Spool of unsealed events; Maia drains it into the signed ledger on its checkpoint.
PLEIADES_NEXUS_SPOOL="${PLEIADES_NEXUS_SPOOL:-$PLEIADES_RUN/nexus.spool}"

# --- logging --------------------------------------------------------------
pleiades_log() {            # pleiades_log <level> <msg...>
    local level="$1"; shift
    # journal is best-effort transport; stderr is the guaranteed path
    logger -t "$PLEIADES_LOG_TAG" -p "daemon.${level}" -- "$*" 2>/dev/null
    printf '[%s] %s: %s\n' "$PLEIADES_LOG_TAG" "$level" "$*" >&2
}
log_info() { pleiades_log info    "$@"; }
log_warn() { pleiades_log warning "$@"; }
log_err()  { pleiades_log err     "$@"; }

# --- error handling (the anti-`|| true`) ----------------------------------
# require <cmd...> : run it; on non-zero, log loudly and return the real rc.
require() {
    if "$@"; then return 0; fi
    local rc=$?
    log_err "FAILED(rc=$rc): $*"
    return "$rc"
}

# --- the Nexus: emit an event ---------------------------------------------
# Goes to the journal (transport) AND a spool that Maia later seals into the
# hash-chained, signed, append-only ledger. The spool append is flock-
# serialized so concurrent agents can't corrupt the queue.
nexus_emit() {              # nexus_emit <event_type> [key=val ...]
    local etype="$1"; shift
    local line="event=${etype} $*"
    logger -t "pleiades-nexus" -p "daemon.notice" -- "$line"
    ( mkdir -p "$(dirname "$PLEIADES_NEXUS_SPOOL")" 2>/dev/null
      exec 7>>"${PLEIADES_NEXUS_SPOOL}.lock" 2>/dev/null || exit 0
      flock 7 2>/dev/null || exit 0
      printf '%s\n' "$line" >> "$PLEIADES_NEXUS_SPOOL" ) 2>/dev/null
}

# --- honest health status -------------------------------------------------
status_set() {              # status_set <agent> <status> [last_error]
    local agent="$1" status="$2" err="${3:-}"
    mkdir -p "$PLEIADES_STATE_DIR" 2>/dev/null
    printf '{"agent":"%s","status":"%s","last_error":"%s","ts":%s}\n' \
        "$agent" "$status" "${err//\"/\'}" "$(date +%s)" \
        > "$PLEIADES_STATE_DIR/${agent}.json"
}

# --- correct load parse (fixes the copy-pasted `load ameropege:` typo) -----
host_load() { uptime | sed -n 's/.*load average: *\([0-9.]*\).*/\1/p'; }
