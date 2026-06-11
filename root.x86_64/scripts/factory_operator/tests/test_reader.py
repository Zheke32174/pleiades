import pytest
import json
import os
from factory_operator.reader import TaskMasterReader

@pytest.fixture
def sample_tasks_file(tmp_path):
    tasks_data = {
        "master": {
            "tasks": [
                {"id": 1, "title": "Task 1", "status": "done", "dependencies": [], "priority": "high"},
                {"id": 2, "title": "Task 2", "status": "pending", "dependencies": [1], "priority": "high"},
                {"id": 3, "title": "Task 3", "status": "pending", "dependencies": [2], "priority": "medium"},
                {"id": 4, "title": "Task 4", "status": "in-progress", "dependencies": [], "priority": "low"}
            ]
        }
    }
    file_path = tmp_path / "tasks.json"
    with open(file_path, "w") as f:
        json.dump(tasks_data, f)
    return file_path

def test_read_tasks(sample_tasks_file):
    reader = TaskMasterReader(sample_tasks_file)
    tasks = reader.read_tasks()
    assert len(tasks) == 4
    assert tasks[0]['id'] == 1

def test_read_tasks_file_not_found(tmp_path):
    reader = TaskMasterReader(tmp_path / "missing.json")
    assert reader.read_tasks() == []

def test_get_pending_tasks(sample_tasks_file):
    reader = TaskMasterReader(sample_tasks_file)
    pending = reader.get_pending_tasks()
    assert len(pending) == 3
    ids = [t['id'] for t in pending]
    assert 2 in ids
    assert 3 in ids
    assert 4 in ids
    assert 1 not in ids

def test_get_next_task(sample_tasks_file):
    reader = TaskMasterReader(sample_tasks_file)
    next_task = reader.get_next_task()
    assert next_task['id'] == 2

def test_dependency_not_satisfied(sample_tasks_file):
    tasks_data = {
        "master": {
            "tasks": [
                {"id": 1, "title": "Task 1", "status": "pending", "dependencies": [], "priority": "low"},
                {"id": 2, "title": "Task 2", "status": "pending", "dependencies": [1], "priority": "high"}
            ]
        }
    }
    with open(sample_tasks_file, "w") as f:
        json.dump(tasks_data, f)

    reader = TaskMasterReader(sample_tasks_file)
    next_task = reader.get_next_task()
    assert next_task['id'] == 1

def test_get_next_task_all_deps_unsatisfied(tmp_path):
    tasks_data = {
        "master": {
            "tasks": [
                {"id": 1, "title": "Task 1", "status": "pending", "dependencies": [99], "priority": "high"},
            ]
        }
    }
    f = tmp_path / "tasks.json"
    f.write_text(json.dumps(tasks_data))
    reader = TaskMasterReader(f)
    assert reader.get_next_task() is None
