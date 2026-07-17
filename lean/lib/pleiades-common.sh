# pleiades-common.sh — shared helpers for the lean Pleiades stack.
# Source me; do not execute. No Termux assumptions. No error masking.
#
# Invariants:
#   * failures are logged and surfaced, never swallowed
#   * agents publish atomic honest status JSON
#   * every Nexus event carries a stable event ID, source and timestamp

PLEIADES_RUN="${PLEIADES_RUN:-/run/pleiades}"
PLEIADES_STATE_DIR="${PLEIADES_STATE_DIR:-$PLEIADES_RUN/state}"
PLEIADES_LOG_TAG="${PLEIADES_LOG_TAG:-pleiades}"
PLEIADES_NEXUS_SPOOL="${PLEIADES_NEXUS_SPOOL:-$PLEIADES_RUN/nexus.spool}"

# --- logging --------------------------------------------------------------
pleiades_log() {
    local level="$1"; shift
    logger -t "$PLEIADES_LOG_TAG" -p "daemon.${level}" -- "$*" 2>/dev/null || :
    printf '[%s] %s: %s\n' "$PLEIADES_LOG_TAG" "$level" "$*" >&2
}
log_info() { pleiades_log info    "$@"; }
log_warn() { pleiades_log warning "$@"; }
log_err()  { pleiades_log err     "$@"; }

# --- error handling -------------------------------------------------------
require() {
    if "$@"; then return 0; fi
    local rc=$?
    log_err "FAILED(rc=$rc): $*"
    return "$rc"
}

# --- identifiers ----------------------------------------------------------
pleiades_event_id() {
    if [[ -r /proc/sys/kernel/random/uuid ]]; then
        tr -d '\n' < /proc/sys/kernel/random/uuid
    elif command -v uuidgen >/dev/null 2>&1; then
        uuidgen
    else
        printf '%s-%s-%s' "$(date +%s%N)" "$$" "$RANDOM"
    fi
}

# --- the Nexus: submit an event ------------------------------------------
# The journal is useful transport, but the flock-serialized spool is the
# acknowledgement boundary for the current lean implementation. If the spool
# cannot accept the record, this function returns non-zero and reports it.
nexus_emit() {
    local etype="${1:?nexus_emit <event_type> [key=val ...]}"; shift
    local event_id observed line rc
    event_id="$(pleiades_event_id)"
    observed="$(date +%s)"
    line="event_id=${event_id} event=${etype} source=${PLEIADES_LOG_TAG} observed_at=${observed} $*"

    if ! logger -t pleiades-nexus -p daemon.notice -- "$line"; then
        printf '[%s] warning: journal transport failed for event_id=%s\n' "$PLEIADES_LOG_TAG" "$event_id" >&2
    fi

    if ! mkdir -p "$(dirname "$PLEIADES_NEXUS_SPOOL")"; then
        log_err "nexus: cannot create spool directory for event_id=$event_id"
        return 1
    fi

    (
        exec 7>>"${PLEIADES_NEXUS_SPOOL}.lock" || exit 1
        flock 7 || exit 1
        printf '%s\n' "$line" >> "$PLEIADES_NEXUS_SPOOL"
    )
    rc=$?
    if [[ "$rc" -ne 0 ]]; then
        log_err "nexus: durable spool append failed rc=$rc event_id=$event_id"
        return "$rc"
    fi
    return 0
}

# --- honest health status -------------------------------------------------
status_set() {
    local agent="$1" status="$2" err="${3:-}" tmp
    if ! mkdir -p "$PLEIADES_STATE_DIR"; then
        log_err "status: cannot create $PLEIADES_STATE_DIR"
        return 1
    fi
    tmp="$(mktemp "$PLEIADES_STATE_DIR/.${agent}.XXXXXX")" || {
        log_err "status: cannot create temporary status for $agent"
        return 1
    }
    printf '{"agent":"%s","status":"%s","last_error":"%s","ts":%s}\n' \
        "$agent" "$status" "${err//\"/\'}" "$(date +%s)" > "$tmp" || {
        rm -f "$tmp"
        log_err "status: write failed for $agent"
        return 1
    }
    mv -f "$tmp" "$PLEIADES_STATE_DIR/${agent}.json"
}

# --- correct load parse ---------------------------------------------------
host_load() { uptime | sed -n 's/.*load average: *\([0-9.]*\).*/\1/p'; }
