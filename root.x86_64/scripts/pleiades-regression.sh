#!/usr/bin/env bash
# Source configuration
source /etc/purple/pleiades.conf 2>/dev/null || source "$(dirname "$0")/../etc/purple/pleiades.conf"
# Purple-team regression harness — syntax, runtime, broker, and host checks
# Usage: bash pleiades-regression.sh [--skip-container]

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPORT_DIR="/var/log/pleiades-regression"
PASS=0
FAIL=0
SKIP=0
SKIP_CONTAINER="${1:-}"

SCRIPTS=(Maia Taygete Alcyone Electra Celaeno Sterope Merope Atlas)
SERVICE_UNITS=(
    taygete-omniversal.service
    alcyone-omniversal.service
    pleiades-rebirth-omniversal.service
    atlas-omniversal.service
    celaeno-omniversal.service
    electra-omniversal.service
    pleiades-nexus-omniversal.service
    maia.service
    host-bridge-monitor.service
    windows-host-bridge-monitor.service
    pleiades-adaptive-builder.service
    pleiades-request-broker.service
)
CONTAINER_PID=""

pass() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $1"; }
skip() { SKIP=$((SKIP + 1)); echo "  SKIP: $1"; }

run_group() {
    local name="$1"
    shift
    echo ""
    echo "=== $name ==="
    "$@" || true
}

skip_group_fast_path() {
    skip "$1 (--skip-container fast path)"
}

ensure_report_dir() {
    mkdir -p "$REPORT_DIR" 2>/dev/null && [[ -w "$REPORT_DIR" ]] && return 0
    REPORT_DIR="/tmp/pleiades-regression"
    mkdir -p "$REPORT_DIR"
}

container_up() {
    local leader nspawn inner

    leader="$(machinectl show pleiades-dr 2>/dev/null | awk -F= '/^Leader=/{print $2}')"
    if [[ -n "$leader" && "$leader" -gt 1 ]]; then
        CONTAINER_PID="$leader"
        return 0
    fi

    nspawn="$(pgrep -x systemd-nspawn | head -1 2>/dev/null || true)"
    if [[ -n "$nspawn" ]]; then
        inner="$(pgrep -P "$nspawn" 2>/dev/null | head -1 || true)"
        if [[ -n "$inner" ]]; then
            CONTAINER_PID="$inner"
            return 0
        fi
    fi

    CONTAINER_PID=""
    return 1
}

in_container() {
    sudo nsenter -t "$CONTAINER_PID" -m -u -i -n -p -- bash -c "$1" 2>/dev/null
}

summary() {
    echo ""
    echo "════════════════════════════════════"
    echo "  PASS=$PASS  FAIL=$FAIL  SKIP=$SKIP"
    echo "════════════════════════════════════"
    ensure_report_dir
    cat > "$REPORT_DIR/last-run.json" <<JSON
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "pass": $PASS,
  "fail": $FAIL,
  "skip": $SKIP,
  "result": "$([ "$FAIL" -eq 0 ] && echo PASS || echo FAIL)"
}
JSON
    echo "  Report: $REPORT_DIR/last-run.json"
    [[ "$FAIL" -eq 0 ]]
}

ensure_report_dir
echo "Purple-team regression harness — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
container_up && echo "Container PID: $CONTAINER_PID" || echo "Container: DOWN"

LIB="$SCRIPT_DIR/pleiades-regression-lib.sh"
if [[ ! -f "$LIB" ]]; then
    fail "Advanced tests missing: $LIB"
    summary
    exit 1
fi

# shellcheck source=pleiades-regression-lib.sh
source "$LIB"

run_group "Syntax gate" test_syntax_gate

if [[ "$SKIP_CONTAINER" == "--skip-container" ]]; then
    run_group "Service active sweep" skip_group_fast_path "service active sweep"
    run_group "Partial start detection" skip_group_fast_path "partial start detection"
    run_group "Decoy port liveness" skip_group_fast_path "decoy port liveness"
    run_group "Taygete concurrency cap" skip_group_fast_path "Taygete concurrency cap"
    run_group "Hostile-recon replay" skip_group_fast_path "hostile-recon replay"
    run_group "Policy broker deny matrix" skip_group_fast_path "policy broker deny matrix"
    run_group "Host bridge mounts" skip_group_fast_path "host bridge mounts"
    run_group "Windows host-bridge snapshots" skip_group_fast_path "Windows host-bridge snapshots"
    run_group "Celaeno liveness" skip_group_fast_path "Celaeno liveness"
    run_group "Maia crypto round-trip" skip_group_fast_path "Maia crypto round-trip"
    run_group "Event log file type" skip_group_fast_path "event log file type"
    run_group "Deterministic policy file" skip_group_fast_path "deterministic policy file"
    run_group "Host heartbeat status" test_host_heartbeat_status
    run_group "Backup archive validity" test_backup_archives
    run_group "pleiadesctl CLI" skip_group_fast_path "pleiadesctl CLI"
    run_group "Alien sidecar authority" skip_group_fast_path "alien sidecar authority"
    run_group "LLM stack (task #30)" skip_group_fast_path "LLM stack"
    run_group "RE pipeline (task #31)" skip_group_fast_path "RE pipeline"
    summary
    exit $?
fi

run_group "Service active sweep" test_services_active
run_group "Partial start detection"             test_partial_start_detection
run_group "Decoy port liveness"                 test_decoy_port_liveness
run_group "Taygete concurrency cap"             test_taygete_concurrency_cap
run_group "Hostile-recon replay"                test_recon_replay
run_group "Policy broker deny matrix"           test_broker_deny_matrix
run_group "Host bridge mounts"                  test_host_bridge_mounts
run_group "Windows host-bridge snapshots"       test_windows_host_bridge_snapshots
run_group "Celaeno liveness"                    test_celaeno_alive
run_group "Maia crypto round-trip"              test_maia_crypto
run_group "Event log file type"                 test_nexus_fifo_regular_file
run_group "Deterministic policy file"           test_policy_file_deterministic
run_group "Host heartbeat status"               test_host_heartbeat_status
run_group "Backup archive validity"             test_backup_archives
run_group "pleiadesctl CLI"                     test_pleiadesctl_cli
run_group "Alien sidecar authority"             test_alien_sidecar_advisory_only
run_group "LLM stack (task #30)"                test_llm_stack
run_group "RE pipeline (task #31)"              test_re_pipeline

summary
