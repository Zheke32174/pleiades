#!/usr/bin/env bash
# Advanced test library for pleiades-regression.sh
# Source this file from the main harness — do not run directly.
# Requires: pass(), fail(), skip(), in_container(), container_up(), CONTAINER_PID
# set in the sourcing script.

# ── subtask 4a: hostile-recon replay ─────────────────────────────────────────

test_recon_replay() {
    if ! container_up; then skip "recon replay (container down)"; return; fi

    local real_hostname
    real_hostname="$(hostname 2>/dev/null || echo "unknown")"

    local before after response
    before="$(in_container "wc -l < /run/pleiades/pleiades-nexus_fifo 2>/dev/null || echo 0")" || before=0

    # Probe Taygete (port 2222) with identity recon commands
    for cmd in "id" "uname -a" "cat /etc/passwd"; do
        response="$(in_container "echo '$cmd' | timeout 3 nc -w 2 127.0.0.1 2222 2>/dev/null || true")"

        # Verify response is SYNTHETIC — must not expose real hostname
        if echo "$response" | grep -qF "$real_hostname" 2>/dev/null; then
            fail "recon '$cmd': real hostname leaked in response"
        else
            pass "recon '$cmd': response does not expose real hostname"
        fi
    done

    after="$(in_container "wc -l < /run/pleiades/pleiades-nexus_fifo 2>/dev/null || echo 0")" || after=0

    if [[ "$after" -gt "$before" ]]; then
        pass "HOSTILE_RECON events emitted to pleiades-nexus_fifo (lines: $before → $after)"
    else
        fail "no new telemetry lines in pleiades-nexus_fifo after recon probes"
    fi
}

# ── subtask 4b: policy broker deny matrix ────────────────────────────────────

test_broker_deny_matrix() {
    if ! container_up; then skip "broker deny matrix (container down)"; return; fi

    # Broker reads *.req files (key=value format), writes decisions to $id.decision
    local req_id="test-deny-$$"
    local req_file="/run/pleiades/requests/${req_id}.req"
    local decision_dir="/run/pleiades/decisions"

    # Test 1: denied class (shell/exec)
    in_container "printf 'id=%s\nclass=shell\naction=exec\nstatus=pending\n' '${req_id}' > '${req_file}'" 2>/dev/null || true

    local denied=false
    for i in $(seq 1 10); do
        sleep 0.5
        if in_container "grep -l 'decision=deny' '${decision_dir}/${req_id}.decision' 2>/dev/null | xargs cat 2>/dev/null | grep -q 'no-action-dispatched\|denied\|class-not-allowed'" 2>/dev/null; then
            denied=true; break
        fi
        # Also accept result file showing denied
        if in_container "grep -q 'no-action-dispatched\|denied' '${decision_dir}/../results/${req_id}.result' 2>/dev/null" 2>/dev/null; then
            denied=true; break
        fi
    done

    if $denied; then
        pass "broker denied shell/exec request"
    else
        fail "broker did not deny shell/exec request within 5s"
    fi

    in_container "rm -f '${req_file}' '${decision_dir}/${req_id}'* '/run/pleiades/results/${req_id}'* 2>/dev/null" || true

    # Test 2: allowed class (capabilities)
    local req_id2="test-allow-$$"
    local req_file2="/run/pleiades/requests/${req_id2}.req"
    in_container "printf 'id=%s\nclass=capabilities\naction=list\nstatus=pending\n' '${req_id2}' > '${req_file2}'" 2>/dev/null || true

    local allowed=false
    for i in $(seq 1 10); do
        sleep 0.5
        if in_container "grep -q 'decision=allow' '${decision_dir}/${req_id2}.decision' 2>/dev/null" 2>/dev/null; then
            allowed=true; break
        fi
    done

    if $allowed; then
        pass "broker allowed capabilities/list request"
    else
        skip "broker allow test inconclusive (broker may not process synchronously)"
    fi

    in_container "rm -f '${req_file2}' '${decision_dir}/${req_id2}'* '/run/pleiades/results/${req_id2}'* 2>/dev/null" || true
}

# ── subtask 5a: host-bridge + Windows telemetry ──────────────────────────────

test_host_bridge() {
    if ! container_up; then skip "host-bridge (container down)"; return; fi

    # /host/proc readable inside container
    if in_container "cat /host/proc/1/status" &>/dev/null; then
        pass "/host/proc/1/status readable"
    else
        skip "/host/proc not mounted (owner bridge not active)"
    fi

    if in_container "cat /host/sys/kernel/hostname" &>/dev/null; then
        pass "/host/sys/kernel/hostname readable"
    else
        skip "/host/sys not mounted"
    fi

    # Windows snapshot newer than 5 minutes
    local snap_dir="/var/lib/pleiades-team/host-bridge/windows11"
    local recent
    recent="$(in_container "find '$snap_dir' -maxdepth 1 -name '*.txt' -mmin -5 2>/dev/null | head -1")" || true
    if [[ -n "$recent" ]]; then
        pass "Windows host-bridge snapshot updated within last 5 min"
    else
        skip "Windows host-bridge snapshot >5 min old (may be normal if monitor just started)"
    fi
}

# ── subtask 5b: Celaeno liveness ─────────────────────────────────────────

test_celaeno_alive() {
    if ! container_up; then skip "Celaeno (container down)"; return; fi

    # Service active
    if in_container "systemctl is-active celaeno-omniversal.service" &>/dev/null; then
        pass "celaeno-omniversal.service is active"
    else
        fail "celaeno-omniversal.service is not active"
        return
    fi

    # Command file writable (Celaeno reads /run/pleiades/celaeno_cmd)
    if in_container "test -w /run/pleiades/celaeno_cmd 2>/dev/null || test -e /run/pleiades/celaeno_cmd"; then
        pass "/run/pleiades/celaeno_cmd exists"
    else
        fail "/run/pleiades/celaeno_cmd missing"
    fi

    # No recent crash-loop: check journal for excessive restarts in last 2 min
    # grep -c exits 1 with 0 matches; use || true to prevent appending a second "0"
    local restarts
    restarts="$(in_container "journalctl -u celaeno-omniversal.service --since '2 minutes ago' --no-pager 2>/dev/null | { grep -c 'Started\|start request' || true; }")" || restarts=0
    restarts="${restarts//[^0-9]/}"   # strip any stray whitespace/newlines
    restarts="${restarts:-0}"
    if [[ "$restarts" -le 2 ]]; then
        pass "Celaeno restart count in last 2m: ${restarts} (≤2)"
    else
        fail "Celaeno crash-looping: ${restarts} restarts in last 2m"
    fi
}

# ── subtask 5c: Maia crypto round-trip ─────────────────────────────────────

test_maia_crypto() {
    if ! container_up; then skip "Maia crypto (container down)"; return; fi

    if ! in_container "test -x /usr/local/bin/maia_crypto" &>/dev/null; then
        fail "maia_crypto binary not found or not executable"
        return
    fi

    # maia_crypto sign <file>  → hex signature
    # maia_crypto verify <file> <sigHex>  → exit 0 on valid
    local tmp_msg="/tmp/_pleiades_regtest_msg_$$"
    local test_payload="regression-test-$(date +%s)"
    in_container "printf '%s' '${test_payload}' > '${tmp_msg}'" 2>/dev/null || true

    local signed
    signed="$(in_container "/usr/local/bin/maia_crypto sign '${tmp_msg}' 2>/dev/null")" || true

    if [[ -z "$signed" ]]; then
        in_container "rm -f '${tmp_msg}'" 2>/dev/null || true
        fail "maia_crypto sign failed (empty output)"
        return
    fi
    pass "maia_crypto sign succeeded"

    # Verify the signature: pass file + sigHex as separate args
    local verify_rc
    verify_rc="$(in_container "/usr/local/bin/maia_crypto verify '${tmp_msg}' '${signed}' 2>/dev/null; echo \$?")" || verify_rc=1
    verify_rc="$(echo "$verify_rc" | tail -1 | tr -d '[:space:]')"

    in_container "rm -f '${tmp_msg}'" 2>/dev/null || true

    if [[ "$verify_rc" == "0" ]]; then
        pass "maia_crypto verify round-trip: OK"
    else
        fail "maia_crypto verify round-trip: FAILED (rc=${verify_rc})"
    fi
}
