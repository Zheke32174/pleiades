import pytest
from factory_operator.proposal import ProposalEngine

def test_classify_safe_task():
    engine = ProposalEngine()
    task = {"id": 1, "title": "Check status", "description": "Run ls and cat to verify state"}
    proposal = engine.classify_task(task)
    assert proposal['risk_level'] == "L0"
    assert proposal['approval_required'] is False

def test_classify_buffered_task():
    engine = ProposalEngine()
    task = {"id": 2, "title": "Update config", "description": "Write new settings to file"}
    proposal = engine.classify_task(task)
    assert proposal['risk_level'] == "L1"
    assert proposal['approval_required'] is True

def test_classify_risky_task():
    engine = ProposalEngine()
    task = {"id": 3, "title": "Restart service", "description": "Use systemctl to restart the daemon"}
    proposal = engine.classify_task(task)
    assert proposal['risk_level'] == "L2"
    assert proposal['approval_required'] is True

def test_classify_outward_task():
    engine = ProposalEngine()
    task = {"id": 4, "title": "Sync to cloud", "description": "Run git push to remote repository"}
    proposal = engine.classify_task(task)
    assert proposal['risk_level'] == "L4"
    assert proposal['approval_required'] is True
