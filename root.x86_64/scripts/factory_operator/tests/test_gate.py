import pytest
import json
import time
from pathlib import Path
from unittest.mock import patch
from factory_operator.gate import ApprovalGate

@pytest.fixture
def gate_dirs(tmp_path):
    outbox = tmp_path / "outbox"
    inbox = tmp_path / "inbox"
    outbox.mkdir()
    inbox.mkdir()
    return outbox, inbox

def test_gate_auto_approve_l0(gate_dirs):
    outbox, inbox = gate_dirs
    gate = ApprovalGate(outbox_dir=outbox, inbox_dir=inbox)
    proposal = {"task_id": 1, "risk_level": "L0", "approval_required": False}
    assert gate.request_approval(proposal) is True
    assert len(list(outbox.glob("*.json"))) == 0

def test_gate_cli_approve(gate_dirs):
    outbox, inbox = gate_dirs
    gate = ApprovalGate()
    proposal = {"task_id": 2, "title": "Test Task", "risk_level": "L1", "approval_required": True}

    with patch('builtins.input', return_value='y'):
        assert gate.request_approval(proposal, mode="cli") is True

def test_gate_cli_deny(gate_dirs):
    outbox, inbox = gate_dirs
    gate = ApprovalGate()
    proposal = {"task_id": 3, "title": "Test Task", "risk_level": "L1", "approval_required": True}

    with patch('builtins.input', return_value='n'):
        assert gate.request_approval(proposal, mode="cli") is False

def test_gate_cli_eoferror_returns_false():
    gate = ApprovalGate()
    proposal = {"task_id": 6, "title": "Test Task", "risk_level": "L1", "approval_required": True}

    with patch('builtins.input', side_effect=EOFError):
        assert gate.request_approval(proposal, mode="cli") is False

def test_gate_cli_keyboard_interrupt_returns_false():
    gate = ApprovalGate()
    proposal = {"task_id": 7, "title": "Test Task", "risk_level": "L1", "approval_required": True}

    with patch('builtins.input', side_effect=KeyboardInterrupt):
        assert gate.request_approval(proposal, mode="cli") is False

def test_gate_programmatic_approve(gate_dirs):
    outbox, inbox = gate_dirs
    gate = ApprovalGate(outbox_dir=outbox, inbox_dir=inbox, timeout=5)
    proposal = {"task_id": 4, "title": "Test Task", "risk_level": "L1", "approval_required": True}

    approval_file = inbox / "approval_4.json"
    with open(approval_file, "w") as f:
        json.dump({"approved": True}, f)

    assert gate.request_approval(proposal, mode="programmatic") is True
    assert (outbox / "proposal_4.json").exists()

def test_gate_programmatic_timeout(gate_dirs):
    outbox, inbox = gate_dirs
    gate = ApprovalGate(outbox_dir=outbox, inbox_dir=inbox, timeout=1)
    proposal = {"task_id": 5, "title": "Test Task", "risk_level": "L1", "approval_required": True}

    assert gate.request_approval(proposal, mode="programmatic") is False

def test_gate_programmatic_no_dirs_raises():
    gate = ApprovalGate()
    proposal = {"task_id": 8, "title": "Test Task", "risk_level": "L1", "approval_required": True}

    with pytest.raises(ValueError, match="Outbox/Inbox"):
        gate.request_approval(proposal, mode="programmatic")

def test_gate_programmatic_corrupt_approval_file(gate_dirs):
    outbox, inbox = gate_dirs
    gate = ApprovalGate(outbox_dir=outbox, inbox_dir=inbox, timeout=2)
    proposal = {"task_id": 9, "title": "Test Task", "risk_level": "L1", "approval_required": True}

    approval_file = inbox / "approval_9.json"
    approval_file.write_text("not valid json")

    result = gate.request_approval(proposal, mode="programmatic")
    assert result is False
