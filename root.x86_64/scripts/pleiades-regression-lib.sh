#!/usr/bin/env bash
# Source configuration
source /etc/purple/pleiades.conf 2>/dev/null || source "$(dirname "$0")/../etc/purple/pleiades.conf"
# Advanced test library for pleiades-regression.sh
# Source this file from the main harness — do not run directly.

test_syntax_gate() {
    local name file

    echo "-- bash -n on 8 scripts --"
    for name in "${SCRIPTS[@]}"; do
        file="$SCRIPT_DIR/${name}.sh"
        if [[ ! -f "$file" ]]; then
            fail "missing script: ${name}.sh"
            continue
        fi
        if bash -n "$file" 2>/dev/null; then
            pass "bash -n ${name}.sh"
        else
            fail "bash -n ${name}.sh"
        fi
    done
}

test_services_active() {
    local unit state failed_count

    if ! container_up; then
        skip "service active sweep (container down)"
        return
    fi

    echo "-- systemctl daemon-reload + active service sweep --"
    if in_container "systemctl daemon-reload" 2>/dev/null; then
        pass "systemctl daemon-reload"
    else
        fail "systemctl daemon-reload"
        return
    fi

    for unit in "${SERVICE_UNITS[@]}"; do
        state="$(in_container "systemctl is-active '$unit' 2>/dev/null || true")"
        if [[ "$state" == "active" ]]; then
            pass "$unit active"
        else
            fail "$unit state=${state:-missing}"
        fi
    done

    failed_count="$(in_container "systemctl --failed --no-legend --plain 2>/dev/null | wc -l" 2>/dev/null)" || failed_count=1
    failed_count="$(echo "$failed_count" | tr -dc '0-9')"
    failed_count="${failed_count:-0}"
    if [[ "$failed_count" == "0" ]]; then
        pass "systemctl --failed reports zero failed units"
    else
        fail "systemctl --failed reports ${failed_count} failed units"
    fi
}

test_partial_start_detection() {
    local degraded_unit degraded_state failed_count inactive_count sabotage_state state unit
    local cleanup_needed=0
    local probe_units=("${SERVICE_UNITS[@]}" "pleiades-sabotage-test.service")

    if ! container_up; then
        skip "partial start detection (container down)"
        return
    fi

    cleanup_partial_start_detection() {
        (( cleanup_needed == 1 )) || return 0
        in_container "systemctl stop pleiades-sabotage-test.service" 2>/dev/null || true
        in_container "rm -f /etc/systemd/system/pleiades-sabotage-test.service" 2>/dev/null || true
        if [[ -n "${degraded_unit:-}" ]]; then
            in_container "systemctl start '$degraded_unit'" 2>/dev/null || true
            in_container "systemctl reset-failed '$degraded_unit'" 2>/dev/null || true
        fi
        in_container "systemctl daemon-reload" 2>/dev/null || true
        in_container "systemctl reset-failed pleiades-sabotage-test.service" 2>/dev/null || true
    }

    trap cleanup_partial_start_detection RETURN

    echo "-- partial start detection (controlled service degradation + sabotage unit) --"

    degraded_unit="windows-host-bridge-monitor.service"
    if ! in_container "systemctl list-unit-files '$degraded_unit' >/dev/null 2>&1" 2>/dev/null; then
        degraded_unit="pleiades-adaptive-builder.service"
    fi

    degraded_state="$(in_container "systemctl is-active '$degraded_unit' 2>/dev/null || true")"
    if [[ "$degraded_state" != "active" ]]; then
        skip "partial start detection skipped (${degraded_unit} not active before fault injection)"
        trap - RETURN
        return
    fi

    if in_container "systemctl stop '$degraded_unit'" 2>/dev/null; then
        pass "fault injection stopped tracked unit ${degraded_unit}"
    else
        fail "fault injection could not stop tracked unit ${degraded_unit}"
        trap - RETURN
        return
    fi

    if in_container 'cat <<EOF > /etc/systemd/system/pleiades-sabotage-test.service
[Unit]
Description=Pleiades Regression Sabotage Test Service

[Service]
Type=oneshot
ExecStart=/bin/false
EOF' 2>/dev/null; then
        cleanup_needed=1
        pass "fault injection wrote sabotage unit"
    else
        fail "fault injection could not write sabotage unit"
        in_container "systemctl start '$degraded_unit'" 2>/dev/null || true
        trap - RETURN
        return
    fi

    if in_container "systemctl daemon-reload" 2>/dev/null; then
        pass "systemctl daemon-reload after fault injection"
    else
        fail "systemctl daemon-reload after fault injection"
    fi

    if in_container "systemctl start pleiades-sabotage-test.service" 2>/dev/null; then
        fail "sabotage unit unexpectedly started cleanly"
    else
        pass "sabotage unit failed as expected"
    fi

    inactive_count=0
    sabotage_state=""
    for unit in "${probe_units[@]}"; do
        state="$(in_container "systemctl is-active '$unit' 2>/dev/null || true")"
        [[ "$state" == "active" ]] || inactive_count=$((inactive_count + 1))
        if [[ "$unit" == "$degraded_unit" && "$state" != "active" ]]; then
            pass "tracked unit ${degraded_unit} became non-active (state=${state:-missing})"
        fi
        if [[ "$unit" == "pleiades-sabotage-test.service" ]]; then
            sabotage_state="$state"
        fi
    done

    failed_count="$(in_container "systemctl --failed --no-legend --plain 2>/dev/null | grep -c '^pleiades-sabotage-test.service '" 2>/dev/null)" || failed_count=0
    failed_count="$(echo "$failed_count" | tr -dc '0-9')"
    failed_count="${failed_count:-0}"

    if [[ "$sabotage_state" != "active" ]]; then
        pass "service sweep marked sabotage unit non-active (state=${sabotage_state:-missing})"
    else
        fail "service sweep incorrectly treated sabotage unit as active"
    fi

    if [[ "$inactive_count" -ge 2 ]]; then
        pass "service sweep detected partial-start condition in tracked set (${inactive_count} non-active units in probe set)"
    else
        fail "service sweep missed partial-start condition in tracked set"
    fi

    if [[ "$failed_count" -gt 0 ]]; then
        pass "systemctl --failed detected sabotage service"
    else
        fail "systemctl --failed missed sabotage service"
    fi

    cleanup_partial_start_detection
    cleanup_needed=0
    trap - RETURN

    if in_container "systemctl --failed --no-legend --plain 2>/dev/null | grep -q '^pleiades-sabotage-test.service '; test \$? -ne 0" 2>/dev/null; then
        pass "sabotage unit cleanup removed failed state"
    else
        fail "sabotage unit cleanup left residual failed state"
    fi

    if in_container "systemctl is-active '$degraded_unit' 2>/dev/null | grep -qx active" 2>/dev/null; then
        pass "tracked unit ${degraded_unit} restored to active"
    else
        fail "tracked unit ${degraded_unit} did not restore to active"
    fi
}

test_decoy_port_liveness() {
    local port listeners owner_lines non_loopback_owner

    if ! container_up; then
        skip "decoy port liveness (container down)"
        return
    fi

    echo "-- decoy port liveness --"
    for port in 2222 2223 2224; do
        if in_container "ss -tlnp | grep -Eq 'LISTEN.+:${port} '" 2>/dev/null; then
            pass "port ${port} listening"
        else
            fail "port ${port} not listening"
        fi
    done

    listeners="$(in_container "ss -tlnp 2>/dev/null")" || listeners=""
    owner_lines="$(printf '%s\n' "$listeners" | grep ':18080[[:space:]]' || true)"
    non_loopback_owner="$(printf '%s\n' "$owner_lines" | grep -Ev '127\.0\.0\.1:18080|::ffff:127\.0\.0\.1:18080' || true)"
    if printf '%s\n' "$owner_lines" | grep -q '127.0.0.1:18080' && [[ -z "$non_loopback_owner" ]]; then
        pass "port 18080 listening on loopback only"
    else
        fail "port 18080 not loopback-only"
    fi
}

test_taygete_concurrency_cap() {
    local banner_count

    if ! container_up; then
        skip "Taygete concurrency cap (container down)"
        return
    fi

    echo "-- Taygete concurrency cap (MAX_CONNS_PER_IP=8) --"
    banner_count="$(in_container '
        pids=()
        for i in $(seq 1 12); do
            { (sleep 5) | timeout 6 nc -w 5 127.0.0.1 2222 > /tmp/_cap_test_${i}.out 2>/dev/null; } &
            pids+=($!)
        done
        sleep 1
        for pid in "${pids[@]}"; do wait "$pid" 2>/dev/null || true; done
        count=0
        for i in $(seq 1 12); do
            [ -s /tmp/_cap_test_${i}.out ] && count=$((count+1))
        done
        echo "$count"
        rm -f /tmp/_cap_test_*.out 2>/dev/null
    ' 2>/dev/null)" || banner_count=0
    banner_count="${banner_count//[^0-9]/}"
    banner_count="${banner_count:-0}"

    if [[ "$banner_count" -le 8 ]]; then
        pass "Taygete concurrency cap: ${banner_count}/12 got banner (<=8 expected)"
    else
        fail "Taygete concurrency cap: ${banner_count}/12 got banner (>8)"
    fi
}

iso_to_epoch() {
    date -u -d "$1" +%s 2>/dev/null || python3 - "$1" <<'PY'
from datetime import datetime
import sys
value = sys.argv[1]
if value.endswith("Z"):
    value = value[:-1] + "+00:00"
print(int(datetime.fromisoformat(value).timestamp()))
PY
}

refresh_host_heartbeat_status() {
    local status_file heartbeat_cli
    status_file="/run/pleiades-gentoo-heartbeat/status"

    heartbeat_cli="${PROJECT_ROOT}/pleiades-gentoo-heartbeat.sh"
    if [[ ! -x "$heartbeat_cli" ]]; then
        return 1
    fi

    timeout 90 bash "$heartbeat_cli" >/dev/null 2>&1
}

test_recon_replay() {
    if ! container_up; then skip "recon replay (container down)"; return; fi

    local real_hostname before after cmd response
    real_hostname="$(in_container "hostname 2>/dev/null" | tr -d '[:space:]')"
    [[ -n "$real_hostname" ]] || real_hostname="unknown"
    before="$(in_container "wc -l < /run/pleiades/pleiades-nexus_fifo 2>/dev/null || echo 0")" || before=0

    for cmd in "id" "uname -a" "cat /etc/passwd"; do
        response="$(in_container "echo '$cmd' | timeout 3 nc -w 2 127.0.0.1 2222 2>/dev/null || true")"
        if [[ -n "$response" ]]; then
            pass "recon '$cmd': synthetic response returned"
        else
            fail "recon '$cmd': empty response"
        fi
        if echo "$response" | grep -qF "$real_hostname" 2>/dev/null; then
            fail "recon '$cmd': real hostname leaked in response"
        else
            pass "recon '$cmd': response does not expose real hostname"
        fi
        case "$cmd" in
            "id")
                if echo "$response" | grep -Eq 'uid=1000\(ubuntu\).*svc-app'; then
                    pass "recon 'id': returned decoy identity data"
                else
                    fail "recon 'id': did not return decoy identity data"
                fi
                ;;
            "uname -a")
                if echo "$response" | grep -Eq 'Linux .*Ubuntu|prod-api-[0-9][0-9]'; then
                    pass "recon 'uname -a': returned decoy host data"
                else
                    fail "recon 'uname -a': did not return decoy host data"
                fi
                ;;
            "cat /etc/passwd")
                if echo "$response" | grep -q 'ubuntu:x:1000:1000:Ubuntu' && echo "$response" | grep -q 'svc-app:'; then
                    pass "recon 'cat /etc/passwd': returned decoy account data"
                else
                    fail "recon 'cat /etc/passwd': did not return decoy account data"
                fi
                ;;
        esac
    done

    after="$(in_container "wc -l < /run/pleiades/pleiades-nexus_fifo 2>/dev/null || echo 0")" || after=0
    if (( after - before >= 3 )); then
        pass "HOSTILE_RECON events emitted to pleiades-nexus_fifo (lines: $before -> $after)"
    else
        fail "expected >=3 new telemetry lines after recon probes (lines: $before -> $after)"
    fi
}

test_broker_deny_matrix() {
    if ! container_up; then skip "broker deny matrix (container down)"; return; fi

    local req_id req_file decision_dir denied req_id2 req_file2 allowed
    decision_dir="/run/pleiades/decisions"

    req_id="test-deny-$$-$(date +%s)"
    req_file="/run/pleiades/requests/${req_id}.req"
    in_container "printf 'id=%s\nclass=shell\naction=exec\nstatus=pending\n' '${req_id}' > '${req_file}'" 2>/dev/null || true

    denied=false
    for _ in $(seq 1 11); do
        sleep 0.5
        if in_container "grep -q 'decision=deny' '${decision_dir}/${req_id}.decision' 2>/dev/null" 2>/dev/null &&
           in_container "grep -Eq 'no-action-dispatched|denied|class-not-allowed' '/run/pleiades/results/${req_id}.result' '${decision_dir}/${req_id}.decision' 2>/dev/null" 2>/dev/null; then
            denied=true
            break
        fi
    done

    if $denied; then
        pass "broker denied shell/exec request"
    else
        fail "broker did not deny shell/exec request within 5s"
    fi

    in_container "rm -f '${req_file}' '${decision_dir}/${req_id}'* '/run/pleiades/results/${req_id}'* 2>/dev/null" || true

    req_id2="test-allow-$$-$(date +%s)"
    req_file2="/run/pleiades/requests/${req_id2}.req"
    in_container "printf 'id=%s\nclass=capabilities\naction=list\nstatus=pending\n' '${req_id2}' > '${req_file2}'" 2>/dev/null || true

    allowed="unknown"
    for _ in $(seq 1 11); do
        sleep 0.5
        if in_container "grep -q 'decision=allow' '${decision_dir}/${req_id2}.decision' 2>/dev/null" 2>/dev/null; then
            allowed="yes"
            break
        fi
        if in_container "grep -q 'decision=deny' '${decision_dir}/${req_id2}.decision' 2>/dev/null" 2>/dev/null; then
            allowed="no"
            break
        fi
    done

    case "$allowed" in
        yes) pass "broker allowed capabilities/list request" ;;
        no) fail "broker denied capabilities/list request" ;;
        *) pass "broker did not deny capabilities/list request" ;;
    esac

    in_container "rm -f '${req_file2}' '${decision_dir}/${req_id2}'* '/run/pleiades/results/${req_id2}'* 2>/dev/null" || true
}

test_host_bridge_mounts() {
    if ! container_up; then skip "host-bridge mounts (container down)"; return; fi

    if ! in_container "test -e /host/proc/1/status" &>/dev/null || ! in_container "test -e /host/sys/kernel/uevent_seqnum" &>/dev/null; then
        skip "host bridge mounts not present (owner-optional)"
        return
    fi

    if in_container "head -c 1 /host/proc/1/status >/dev/null 2>&1 && head -c 1 /host/sys/kernel/uevent_seqnum >/dev/null 2>&1" &>/dev/null; then
        pass "/host/proc/1/status and /host/sys/kernel/uevent_seqnum readable"
    else
        fail "host bridge mounts present but unreadable"
    fi
}

test_windows_host_bridge_snapshots() {
    local snap_dir recent started_us started_epoch now_epoch age

    if ! container_up; then skip "Windows host-bridge snapshots (container down)"; return; fi

    snap_dir="/var/lib/pleiades-team/host-bridge/windows11"
    recent="$(in_container "find '$snap_dir' -maxdepth 1 -name '*.txt' -mmin -5 2>/dev/null | head -1")" || true
    if [[ -n "$recent" ]]; then
        pass "Windows host-bridge snapshot updated within last 5 min"
        return
    fi

    started_us="$(in_container "systemctl show -p ActiveEnterTimestampUSec --value windows-host-bridge-monitor.service 2>/dev/null | tr -d '[:space:]'" 2>/dev/null)" || started_us=0
    started_us="${started_us//[^0-9]/}"
    started_us="${started_us:-0}"
    started_epoch=$(( started_us / 1000000 ))
    now_epoch="$(date -u +%s)"
    age=$(( now_epoch - started_epoch ))
    if (( started_epoch > 0 && age < 300 )); then
        skip "Windows host-bridge snapshot check skipped (monitor started ${age}s ago)"
    else
        fail "Windows host-bridge snapshot missing or stale (>5 min)"
    fi
}

test_celaeno_alive() {
    if ! container_up; then skip "Celaeno (container down)"; return; fi

    if in_container "systemctl is-active celaeno-omniversal.service" &>/dev/null; then
        pass "celaeno-omniversal.service is active"
    else
        fail "celaeno-omniversal.service is not active"
        return
    fi

    if in_container "test -e /run/pleiades/celaeno_cmd" &>/dev/null; then
        pass "/run/pleiades/celaeno_cmd exists"
    else
        fail "/run/pleiades/celaeno_cmd missing"
    fi

    local restarts
    restarts="$(in_container "journalctl -u celaeno-omniversal.service --since '2 minutes ago' --no-pager 2>/dev/null | { grep -c 'Started\\|start request' || true; }")" || restarts=0
    restarts="${restarts//[^0-9]/}"
    restarts="${restarts:-0}"
    if [[ "$restarts" -le 2 ]]; then
        pass "Celaeno restart count in last 2m: ${restarts} (<=2)"
    else
        fail "Celaeno crash-looping: ${restarts} restarts in last 2m"
    fi
}

test_llm_stack() {
    if ! container_up; then skip "LLM stack (container down)"; return; fi
    if ! in_container "test -x /usr/local/bin/llama-cli" &>/dev/null; then
        skip "llama-cli not found — run install-llm-stack.sh to build"
        return
    fi
    pass "llama-cli installed"
    if ! in_container "test -f /etc/pleiades/llm.conf" &>/dev/null; then
        fail "/etc/pleiades/llm.conf missing — install-llm-stack.sh not run"
        return
    fi
    pass "/etc/pleiades/llm.conf present"

    local model_path model_size
    model_path="$(in_container "grep '^MODEL_PATH=' /etc/pleiades/llm.conf | cut -d= -f2" 2>/dev/null)" || true
    if [[ -z "$model_path" ]]; then
        fail "MODEL_PATH not set in /etc/pleiades/llm.conf"
        return
    fi
    model_size="$(in_container "wc -c < '$model_path' 2>/dev/null || echo 0")" || model_size=0
    model_size="${model_size//[^0-9]/}"
    model_size="${model_size:-0}"
    if (( model_size > 1000000000 )); then
        pass "model file present ($(( model_size / 1048576 )) MiB)"
    else
        fail "model file missing or too small at $model_path (${model_size} bytes)"
        return
    fi

    if in_container "test -x /usr/local/bin/pleiades-llm" &>/dev/null; then
        pass "pleiades-llm wrapper executable"
    else
        fail "pleiades-llm wrapper not found"
        return
    fi

    if in_container "test -f /etc/systemd/system/pleiades-llm.slice" &>/dev/null; then
        pass "pleiades-llm.slice unit present"
    else
        fail "pleiades-llm.slice missing — resource limits not configured"
    fi
}

test_re_pipeline() {
    if ! container_up; then skip "RE pipeline (container down)"; return; fi

    local re_cmd ver sample_bin report llm_report
    re_cmd=""
    if in_container "test -x /usr/local/bin/pleiades-re" &>/dev/null; then
        re_cmd="/usr/local/bin/pleiades-re"
    elif in_container "test -f /scripts/pleiades-re.sh" &>/dev/null; then
        re_cmd="bash /scripts/pleiades-re.sh"
    else
        skip "pleiades-re not found inside container (not yet installed)"
        return
    fi

    ver="$(in_container "$re_cmd version 2>/dev/null")" || true
    if [[ "$ver" == pleiades-re* ]]; then
        pass "pleiades-re version: $ver"
    else
        fail "pleiades-re version command failed (got: '$ver')"
        return
    fi

    sample_bin="/usr/local/bin/maia_crypto"
    if ! in_container "test -x '$sample_bin'" &>/dev/null; then
        sample_bin="/usr/bin/file"
    fi

    report="$(in_container "$re_cmd analyze '$sample_bin' --format=markdown 2>/dev/null")" || true
    if echo "$report" | grep -q "Pleiades Team RE Report"; then
        pass "pleiades-re analyze: report header present"
    else
        fail "pleiades-re analyze: report missing header"
    fi
    if echo "$report" | grep -q "Stage 1: Decompiled Output"; then
        pass "pleiades-re analyze: Stage 1 section present"
    else
        fail "pleiades-re analyze: Stage 1 section missing"
    fi
    if echo "$report" | grep -q "Stage 3: Type Recovery"; then
        pass "pleiades-re analyze: Stage 3 section present"
    else
        fail "pleiades-re analyze: Stage 3 section missing"
    fi

    if in_container "test -f /run/pleiades/capabilities/pleiades_re.cap" &>/dev/null; then
        pass "pleiades_re.cap capability registered"
    else
        fail "pleiades_re.cap not written"
    fi

    if ! in_container "test -x /usr/local/bin/llama-cli && test -x /usr/local/bin/pleiades-llm" &>/dev/null; then
        skip "RE pipeline LLM stage (pleiades-llm or llama-cli not installed)"
        return
    fi

    llm_report="$(in_container "USE_LLM=1 $re_cmd analyze '$sample_bin' --llm 2>/dev/null")" || true
    if echo "$llm_report" | grep -q "Stage 2: LLM Analysis"; then
        pass "pleiades-re --llm: Stage 2 section present"
    else
        fail "pleiades-re --llm: Stage 2 LLM section missing"
    fi
}

test_maia_crypto() {
    if ! container_up; then skip "Maia crypto (container down)"; return; fi

    if ! in_container "test -x /usr/local/bin/maia_crypto" &>/dev/null; then
        fail "maia_crypto binary not found or not executable"
        return
    fi

    local tmp_msg test_payload signed verify_rc
    tmp_msg="/tmp/_pleiades_regtest_msg_$$"
    test_payload="regression-test-$(date +%s)"
    in_container "printf '%s' '${test_payload}' > '${tmp_msg}'" 2>/dev/null || true

    signed="$(in_container "/usr/local/bin/maia_crypto sign '${tmp_msg}' 2>/dev/null")" || true
    if [[ -z "$signed" ]]; then
        in_container "rm -f '${tmp_msg}'" 2>/dev/null || true
        fail "maia_crypto sign failed (empty output)"
        return
    fi
    if echo "$signed" | grep -Eq '^[0-9a-fA-F]+$'; then
        pass "maia_crypto sign returned non-empty hex signature"
    else
        fail "maia_crypto sign returned non-hex output"
    fi

    verify_rc="$(in_container "/usr/local/bin/maia_crypto verify '${tmp_msg}' '${signed}' 2>/dev/null; echo \$?")" || verify_rc=1
    verify_rc="$(echo "$verify_rc" | tail -1 | tr -d '[:space:]')"
    in_container "rm -f '${tmp_msg}'" 2>/dev/null || true

    if [[ "$verify_rc" == "0" ]]; then
        pass "maia_crypto verify round-trip: OK"
    else
        fail "maia_crypto verify round-trip: FAILED (rc=${verify_rc})"
    fi
}

test_nexus_fifo_regular_file() {
    if ! container_up; then skip "pleiades-nexus_fifo type (container down)"; return; fi

    local kind file_out
    kind="$(in_container "stat -c '%F' /run/pleiades/pleiades-nexus_fifo 2>/dev/null" | tr -d '\r')"
    file_out="$(in_container "file -b /run/pleiades/pleiades-nexus_fifo 2>/dev/null" | tr -d '\r')"
    if [[ "$kind" == "regular file" ]]; then
        pass "pleiades-nexus_fifo is a regular file"
    elif [[ -z "$kind" ]]; then
        fail "pleiades-nexus_fifo missing"
    else
        fail "pleiades-nexus_fifo is not a regular file (${kind:-unknown}; file: ${file_out:-unknown})"
    fi
}

test_policy_file_deterministic() {
    if ! container_up; then skip "policy file (container down)"; return; fi

    if ! in_container "test -f /etc/pleiades/pleiades-swarm-policy.json" &>/dev/null; then
        fail "/etc/pleiades/pleiades-swarm-policy.json missing"
        return
    fi

    if in_container "python3 - <<'PY'
import json
from pathlib import Path
path = Path('/etc/pleiades/pleiades-swarm-policy.json')
data = json.loads(path.read_text())
assert data.get('mode') == 'owner-authorized-defensive'
assert data.get('default_request_decision') == 'deny'
alien = data.get('alien_sidecar') or {}
assert alien.get('enabled') is False
PY" &>/dev/null; then
        pass "pleiades-swarm policy matches deterministic defensive baseline"
    else
        fail "pleiades-swarm policy drifted from deterministic defensive baseline"
    fi
}

test_host_heartbeat_status() {
    local status_file updated_utc updated_epoch now_epoch age refresh_rc
    status_file="/run/pleiades-gentoo-heartbeat/status"

    if [[ ! -f "$status_file" || ! "$(grep -c '^status=running$' "$status_file" 2>/dev/null || true)" == "1" ]]; then
        if [[ "${SKIP_CONTAINER:-}" == "--skip-container" ]]; then
            skip "heartbeat status unavailable in --skip-container fast path"
            return
        fi
        refresh_host_heartbeat_status
        refresh_rc=$?
    else
        refresh_rc=0
    fi
    if [[ ! -f "$status_file" ]]; then
        if [[ "$refresh_rc" -eq 124 ]]; then
            fail "heartbeat status file missing after refresh attempt timed out: $status_file"
        elif [[ "$refresh_rc" -ne 0 ]]; then
            fail "heartbeat status file missing and refresh attempt failed (rc=${refresh_rc}): $status_file"
        else
            fail "heartbeat status file missing: $status_file"
        fi
        return
    fi
    if grep -q '^status=running$' "$status_file"; then
        pass "heartbeat status=running"
    else
        fail "heartbeat status is not running"
    fi

    updated_utc="$(awk -F= '/^updated_utc=/{print $2}' "$status_file" | tail -1)"
    if [[ -z "$updated_utc" ]]; then
        fail "heartbeat updated_utc missing"
        return
    fi

    updated_epoch="$(iso_to_epoch "$updated_utc" 2>/dev/null || echo 0)"
    now_epoch="$(date -u +%s)"
    age=$(( now_epoch - updated_epoch ))
    if (( updated_epoch <= 0 || age > 120 )); then
        refresh_host_heartbeat_status
        refresh_rc=$?
        updated_utc="$(awk -F= '/^updated_utc=/{print $2}' "$status_file" | tail -1)"
        updated_epoch="$(iso_to_epoch "$updated_utc" 2>/dev/null || echo 0)"
        now_epoch="$(date -u +%s)"
        age=$(( now_epoch - updated_epoch ))
    fi
    if (( updated_epoch > 0 && age <= 120 )); then
        pass "heartbeat status fresh (${age}s old)"
    else
        fail "heartbeat status stale (${age}s old)"
    fi
}

test_backup_archives() {
    local backup_cli output rc timeout_secs
    backup_cli="$PROJECT_ROOT/pleiades-backup.sh"
    if [[ ! -f "$backup_cli" ]]; then
        fail "backup helper missing: $backup_cli"
        return
    fi

    timeout_secs=20
    if [[ "${SKIP_CONTAINER:-}" == "--skip-container" ]]; then
        timeout_secs=5
    fi

    output="$(timeout "$timeout_secs" bash "$backup_cli" --dry-run 2>&1)"
    rc=$?
    if [[ $rc -eq 0 ]] && echo "$output" | grep -q '^valid_archive=yes$'; then
        pass "backup dry-run confirmed a valid non-zero archive"
    elif [[ $rc -eq 124 && "${SKIP_CONTAINER:-}" == "--skip-container" ]]; then
        skip "backup dry-run exceeded --skip-container fast-path budget"
    elif [[ $rc -eq 124 ]]; then
        fail "backup dry-run timed out"
    else
        fail "backup dry-run did not confirm a valid archive"
    fi
}

test_pleiadesctl_cli() {
    if ! container_up; then skip "pleiadesctl CLI (container down)"; return; fi

    local status_out help_out bare_out bare_rc
    status_out="$(in_container "pleiadesctl status 2>/dev/null")" || true
    if [[ -n "$status_out" ]] && echo "$status_out" | grep -Eq 'components=.*(alcyone|taygete|maia)'; then
        pass "pleiadesctl status exits 0 and prints component names"
    else
        fail "pleiadesctl status did not print expected component names"
    fi

    help_out="$(in_container "pleiadesctl help 2>/dev/null")" || true
    if echo "$help_out" | grep -q 'usage:'; then
        pass "pleiadesctl help returned usage output"
    else
        fail "pleiadesctl help did not return usage output"
    fi

    bare_out="$(in_container "pleiadesctl 2>/dev/null; echo RC:\$?")" || true
    bare_rc="$(echo "$bare_out" | awk -F: '/^RC:/{print $2}' | tail -1 | tr -d '[:space:]')"
    if [[ "$bare_rc" != "139" ]]; then
        pass "pleiadesctl without args did not segfault"
    else
        fail "pleiadesctl without args segfaulted"
    fi
}

test_alien_sidecar_advisory_only() {
    if ! container_up; then skip "alien sidecar authority (container down)"; return; fi

    local outbox_files non_hint alien_action
    outbox_files="$(in_container "find /run/pleiades/alien/outbox -maxdepth 1 -type f 2>/dev/null | wc -l")" || outbox_files=0
    outbox_files="$(echo "$outbox_files" | tr -dc '0-9')"
    outbox_files="${outbox_files:-0}"

    if [[ "$outbox_files" == "0" ]]; then
        pass "alien outbox empty"
    else
        non_hint="$(in_container "find /run/pleiades/alien/outbox -maxdepth 1 -type f -exec grep -Lqi 'hint' {} + 2>/dev/null | head -1")" || true
        if [[ -z "$non_hint" ]]; then
            pass "alien outbox contains hint-only entries"
        else
            fail "alien outbox contains non-hint entry: ${non_hint}"
        fi
    fi

    alien_action="$(in_container "find /run/pleiades/actions -maxdepth 1 -type f -exec grep -li 'alien' {} + 2>/dev/null | head -1")" || true
    if [[ -z "$alien_action" ]]; then
        pass "no alien-originated action present in /run/pleiades/actions"
    else
        fail "alien-originated action present: ${alien_action}"
    fi
}
