import json
from pathlib import Path
from typing import List, Dict, Any, Optional

class TaskMasterReader:
    PRIORITY_MAP = {"high": 3, "medium": 2, "low": 1}
    
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.tasks_data: Dict[str, Any] = {}
    
    def read_tasks(self) -> List[Dict[str, Any]]:
        if not self.file_path.exists():
            return []
        with open(self.file_path, "r") as f:
            self.tasks_data = json.load(f)
        return self.tasks_data.get("master", {}).get("tasks", [])
    
    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        tasks = self.read_tasks()
        return [t for t in tasks if t.get("status") in ["pending", "in-progress"]]
    
    def get_next_task(self) -> Optional[Dict[str, Any]]:
        tasks = self.read_tasks()
        pending_tasks = [t for t in tasks if t.get("status") in ["pending", "in-progress"]]
        done_task_ids = {t.get("id") for t in tasks if t.get("status") == "done"}
        
        runnable_tasks = []
        for task in pending_tasks:
            deps = task.get("dependencies", [])
            if all(dep_id in done_task_ids for dep_id in deps):
                runnable_tasks.append(task)
        
        if not runnable_tasks:
            return None
        
        # Sort by priority (descending) and then by original order/ID
        runnable_tasks.sort(key=lambda x: (self.PRIORITY_MAP.get(x.get("priority", "low"), 0), -int(x.get("id", 0))), reverse=True)
        return runnable_tasks[0]
