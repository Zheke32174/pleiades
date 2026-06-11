import pytest
import datetime
from pathlib import Path
from factory_operator.logger import ReceiptLogger

@pytest.fixture
def state_file(tmp_path):
    f = tmp_path / "PLEIADES_STATE.md"
    f.write_text(
        "# Pleiades Team State\n\n"
        "## Recently Changed\n\n"
        "## Agent Communication Log\n"
        "| Date | Agent | Summary |\n"
        "|---|---|---|\n"
    )
    return f

def test_log_receipt_to_communication_log(state_file):
    logger = ReceiptLogger(state_file)
    task = {"id": "1", "title": "Scan network"}
    result = {"status": "completed", "summary": "Found 5 hosts"}

    logger.log_receipt(task, result)

    content = state_file.read_text()
    assert "| Scan network" in content
    assert "Found 5 hosts" in content
    assert "Factory Operator" in content

def test_log_receipt_file_not_found(tmp_path):
    state_file = tmp_path / "NON_EXISTENT.md"
    logger = ReceiptLogger(state_file)
    task = {"id": "1", "title": "Test"}
    result = {"status": "completed", "summary": "Test"}

    logger.log_receipt(task, result)
    assert state_file.exists()

def test_log_recently_changed_adds_entry(state_file):
    logger = ReceiptLogger(state_file)
    logger.log_recently_changed("2026-06-10", "Deployed operator", ["Added service file", "Configured paths"])

    content = state_file.read_text()
    assert "2026-06-10" in content
    assert "Deployed operator" in content
    assert "Added service file" in content
    assert "Configured paths" in content

def test_log_recently_changed_prepends_newest_first(state_file):
    logger = ReceiptLogger(state_file)
    logger.log_recently_changed("2026-06-09", "First change", [])
    logger.log_recently_changed("2026-06-10", "Second change", [])

    content = state_file.read_text()
    assert content.index("Second change") < content.index("First change")

def test_log_recently_changed_caps_at_max_entries(tmp_path):
    state_file = tmp_path / "PLEIADES_STATE.md"
    logger = ReceiptLogger(state_file)
    for i in range(15):
        logger.log_recently_changed(f"2026-06-{i+1:02d}", f"Change {i}", [])

    content = state_file.read_text()
    assert content.count("- **2026") == 10

def test_log_recently_changed_creates_section_if_missing(tmp_path):
    state_file = tmp_path / "STATE.md"
    state_file.write_text("# Pleiades Team State\n\n## Agent Communication Log\n")
    logger = ReceiptLogger(state_file)
    logger.log_recently_changed("2026-06-10", "New change", ["detail"])

    content = state_file.read_text()
    assert "Recently Changed" in content
    assert "New change" in content

def test_log_recently_changed_header_no_trailing_newline(tmp_path):
    # Header present but no trailing newline — hits the regex-fallback else branch.
    state_file = tmp_path / "STATE.md"
    state_file.write_text("# State\n\n## Recently Changed")
    logger = ReceiptLogger(state_file)
    logger.log_recently_changed("2026-06-10", "Edge case", [])

    content = state_file.read_text()
    assert "Edge case" in content
