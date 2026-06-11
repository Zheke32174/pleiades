#!/usr/bin/env python3
"""
Factory Operator Daemon — persistent loop mode for systemd.
Polls for the next runnable task, gates through HITL, dispatches, and logs a receipt.
Exits cleanly when the task queue is empty or on SIGTERM.
"""
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

# Allow running from the scripts directory without installing the package
sys.path.insert(0, str(Path(__file__).parent))

from factory_operator.gate import ApprovalGate
from factory_operator.logger import ReceiptLogger
from factory_operator.proposal import ProposalEngine
from factory_operator.reader import TaskMasterReader

TASKS_FILE    = Path(os.environ.get("TASKMASTER_TASKS",
                     "/workspaces/gentoo/.taskmaster/tasks/tasks.json"))
STATE_FILE    = Path(os.environ.get("PLEIADES_STATE_FILE",
                     "/run/pleiades/PLEIADES_STATE.md"))
OUTBOX_DIR    = Path(os.environ.get("PLEIADES_OUTBOX",
                     "/run/pleiades/alien/outbox"))
INBOX_DIR     = Path(os.environ.get("PLEIADES_INBOX",
                     "/run/pleiades/alien/inbox"))
PID_FILE      = Path(os.environ.get("PLEIADES_OPERATOR_PID",
                     "/run/pleiades/factory_operator.pid"))
POLL_INTERVAL = int(os.environ.get("PLEIADES_POLL_INTERVAL", "30"))

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [factory-operator] %(levelname)s %(message)s")
log = logging.getLogger(__name__)

_running = True

def _handle_sigterm(signum, frame):
    global _running
    log.info("SIGTERM received — stopping after current cycle")
    _running = False

def _write_pid() -> None:
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))

def _remove_pid() -> None:
    PID_FILE.unlink(missing_ok=True)

def _dispatch_task(task: dict, proposal: dict) -> dict:
    """Write the task to the Pleiades request bus and return a synthetic result."""
    request_dir = Path("/run/pleiades/requests")
    request_dir.mkdir(parents=True, exist_ok=True)
    req_file = request_dir / f"task_{task.get('id')}.json"
    req_file.write_text(json.dumps({"task": task, "proposal": proposal}, indent=2))
    log.info("Dispatched task %s → %s", task.get("id"), req_file)
    return {"status": "dispatched", "summary": f"Written to {req_file}"}

def run_cycle(reader: TaskMasterReader, engine: ProposalEngine,
              gate: ApprovalGate, logger: ReceiptLogger) -> bool:
    """
    Execute one operator cycle.
    Returns True if a task was processed, False if queue was empty.
    """
    task = reader.get_next_task()
    if not task:
        return False

    proposal = engine.classify_task(task)
    proposal["title"] = task.get("title", "")
    proposal["description"] = task.get("description", "")
    log.info("Task %s classified as %s (%s)",
             task.get("id"), proposal["risk_level"], proposal["label"])

    approved = gate.request_approval(proposal, mode="programmatic")
    if not approved:
        log.warning("Task %s NOT approved — skipping", task.get("id"))
        logger.log_receipt(task, {"status": "denied", "summary": "HITL approval denied"})
        return True

    result = _dispatch_task(task, proposal)
    logger.log_receipt(task, result)
    return True

def main() -> None:
    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)

    _write_pid()
    log.info("Factory Operator daemon started (PID %d)", os.getpid())

    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    INBOX_DIR.mkdir(parents=True, exist_ok=True)

    reader = TaskMasterReader(TASKS_FILE)
    engine = ProposalEngine()
    gate   = ApprovalGate(outbox_dir=OUTBOX_DIR, inbox_dir=INBOX_DIR, timeout=300)
    logger = ReceiptLogger(STATE_FILE)

    try:
        while _running:
            try:
                had_work = run_cycle(reader, engine, gate, logger)
            except Exception as exc:
                log.error("Cycle error: %s", exc, exc_info=True)
                time.sleep(POLL_INTERVAL)
                continue

            if not had_work:
                log.info("Task queue empty — waiting %ds", POLL_INTERVAL)
                time.sleep(POLL_INTERVAL)
    finally:
        _remove_pid()
        log.info("Factory Operator daemon stopped")

if __name__ == "__main__":
    main()
