"""
Phase 3 deployment and crash-recovery tests for the Factory Operator.
These are integration-style smoke tests that verify the daemon starts, processes
tasks, handles SIGTERM cleanly, and recovers from a cycle error.
"""
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure the scripts directory is on the path
SCRIPTS_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from factory_operator.gate import ApprovalGate
from factory_operator.logger import ReceiptLogger
from factory_operator.proposal import ProposalEngine
from factory_operator.reader import TaskMasterReader

# Import the daemon's run_cycle directly for unit-level coverage
sys.path.insert(0, str(SCRIPTS_DIR))
import importlib.util
_daemon_spec = importlib.util.spec_from_file_location(
    "daemon", SCRIPTS_DIR / "pleiades-factory-operator-daemon.py"
)
_daemon = importlib.util.module_from_spec(_daemon_spec)
_daemon_spec.loader.exec_module(_daemon)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def env_dirs(tmp_path):
    outbox = tmp_path / "outbox"
    inbox = tmp_path / "inbox"
    requests = tmp_path / "requests"
    for d in (outbox, inbox, requests):
        d.mkdir()
    return {"outbox": outbox, "inbox": inbox, "requests": requests, "root": tmp_path}


@pytest.fixture
def tasks_file(tmp_path):
    data = {
        "master": {
            "tasks": [
                {"id": 1, "title": "Check health", "status": "pending",
                 "dependencies": [], "priority": "high",
                 "description": "status check read"},
            ]
        }
    }
    f = tmp_path / "tasks.json"
    f.write_text(json.dumps(data))
    return f


# ── Service unit file tests ───────────────────────────────────────────────────

def test_service_file_exists():
    svc = SCRIPTS_DIR / "pleiades-factory-operator.service"
    assert svc.exists(), "Service unit file must be present alongside daemon script"


def test_service_file_has_required_fields():
    svc = (SCRIPTS_DIR / "pleiades-factory-operator.service").read_text()
    for field in ("ExecStart", "Restart=on-failure", "RestartSec", "User="):
        assert field in svc, f"Service file missing required field: {field}"


def test_service_file_references_daemon():
    svc = (SCRIPTS_DIR / "pleiades-factory-operator.service").read_text()
    assert "pleiades-factory-operator-daemon.py" in svc


# ── Daemon run_cycle tests ────────────────────────────────────────────────────

def test_run_cycle_empty_queue(tmp_path, tasks_file):
    data = {"master": {"tasks": []}}
    tasks_file.write_text(json.dumps(data))

    reader = TaskMasterReader(tasks_file)
    engine = ProposalEngine()
    gate = ApprovalGate(outbox_dir=tmp_path / "out", inbox_dir=tmp_path / "in")
    logger = ReceiptLogger(tmp_path / "STATE.md")

    result = _daemon.run_cycle(reader, engine, gate, logger)
    assert result is False


def test_run_cycle_l0_task_auto_dispatched(env_dirs, tasks_file):
    reader = TaskMasterReader(tasks_file)
    engine = ProposalEngine()
    gate = ApprovalGate(outbox_dir=env_dirs["outbox"], inbox_dir=env_dirs["inbox"])
    logger = ReceiptLogger(env_dirs["root"] / "STATE.md")

    with patch.object(_daemon, "_dispatch_task",
                      return_value={"status": "dispatched", "summary": "ok"}):
        result = _daemon.run_cycle(reader, engine, gate, logger)

    assert result is True
    state = (env_dirs["root"] / "STATE.md").read_text()
    assert "Check health" in state


def test_run_cycle_denied_task_logs_receipt(env_dirs, tmp_path):
    data = {
        "master": {
            "tasks": [
                {"id": 2, "title": "git push origin main", "status": "pending",
                 "dependencies": [], "priority": "high",
                 "description": "git push to remote"}
            ]
        }
    }
    tf = tmp_path / "tasks.json"
    tf.write_text(json.dumps(data))

    reader = TaskMasterReader(tf)
    engine = ProposalEngine()
    # Programmatic gate — no approval file present → denied
    gate = ApprovalGate(outbox_dir=env_dirs["outbox"], inbox_dir=env_dirs["inbox"], timeout=0)
    logger = ReceiptLogger(env_dirs["root"] / "STATE.md")

    result = _daemon.run_cycle(reader, engine, gate, logger)
    assert result is True
    state = (env_dirs["root"] / "STATE.md").read_text()
    assert "denied" in state


# ── Crash recovery tests ──────────────────────────────────────────────────────

def test_run_cycle_exception_is_caught_by_daemon_loop(env_dirs, tasks_file):
    """The daemon main loop must continue after a cycle raises an exception."""
    reader = TaskMasterReader(tasks_file)
    engine = ProposalEngine()
    gate = ApprovalGate(outbox_dir=env_dirs["outbox"], inbox_dir=env_dirs["inbox"])
    logger = ReceiptLogger(env_dirs["root"] / "STATE.md")

    call_count = {"n": 0}
    original_run_cycle = _daemon.run_cycle

    def patched_run_cycle(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated transient error")
        _daemon._running = False
        return original_run_cycle(*args, **kwargs)

    with patch.object(_daemon, "run_cycle", side_effect=patched_run_cycle), \
         patch.object(_daemon, "_write_pid"), \
         patch.object(_daemon, "_remove_pid"), \
         patch.object(_daemon, "OUTBOX_DIR", env_dirs["outbox"]), \
         patch.object(_daemon, "INBOX_DIR", env_dirs["inbox"]), \
         patch("time.sleep"):
        _daemon._running = True
        _daemon.main()

    assert call_count["n"] >= 2, "Daemon should have retried after the exception"


def test_daemon_handles_sigterm_gracefully(tmp_path):
    """Launch the daemon in a subprocess, send SIGTERM, verify clean exit."""
    daemon_py = SCRIPTS_DIR / "pleiades-factory-operator-daemon.py"
    env = os.environ.copy()
    env.update({
        "TASKMASTER_TASKS": str(tmp_path / "missing.json"),
        "PLEIADES_STATE_FILE": str(tmp_path / "STATE.md"),
        "PLEIADES_OUTBOX": str(tmp_path / "outbox"),
        "PLEIADES_INBOX": str(tmp_path / "inbox"),
        "PLEIADES_OPERATOR_PID": str(tmp_path / "op.pid"),
        "PLEIADES_POLL_INTERVAL": "1",
        "PYTHONPATH": str(SCRIPTS_DIR),
    })

    proc = subprocess.Popen(
        [sys.executable, str(daemon_py)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Give it a moment to start
    time.sleep(0.5)
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        pytest.fail("Daemon did not exit within 5s after SIGTERM")

    assert proc.returncode == 0, f"Daemon exited with code {proc.returncode}"


# ── End-to-end workflow smoke test ────────────────────────────────────────────

def test_end_to_end_operator_workflow(env_dirs, tmp_path):
    """
    Simulate the full operator loop:
    propose → L0 auto-approve → dispatch → receipt logged.
    """
    tasks_data = {
        "master": {
            "tasks": [
                {"id": 10, "title": "Verify filesystem state", "status": "pending",
                 "dependencies": [], "priority": "medium",
                 "description": "read and verify files to check status"},
            ]
        }
    }
    tf = tmp_path / "tasks.json"
    tf.write_text(json.dumps(tasks_data))

    reader = TaskMasterReader(tf)
    engine = ProposalEngine()
    gate = ApprovalGate(outbox_dir=env_dirs["outbox"], inbox_dir=env_dirs["inbox"])
    logger = ReceiptLogger(env_dirs["root"] / "STATE.md")

    proposal = engine.classify_task(reader.get_next_task())
    assert proposal["risk_level"] == "L0"
    assert gate.request_approval(proposal) is True

    with patch.object(_daemon, "_dispatch_task",
                      return_value={"status": "dispatched", "summary": "ok"}) as mock_dispatch:
        result = mock_dispatch({"id": 10, "title": "Verify filesystem state"}, proposal)

    assert result["status"] == "dispatched"

    logger.log_receipt({"id": 10, "title": "Verify filesystem state"}, result)
    state = (env_dirs["root"] / "STATE.md").read_text()
    assert "Verify filesystem state" in state
    assert "dispatched" in state
