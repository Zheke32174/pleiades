#!/usr/bin/env python3
import sys
import json
from pathlib import Path
from factory_operator.reader import TaskMasterReader
from factory_operator.proposal import ProposalEngine

TASKS_FILE = "/workspaces/gentoo/.taskmaster/tasks/tasks.json"

def propose_next():
    reader = TaskMasterReader(TASKS_FILE)
    engine = ProposalEngine()
    
    next_task = reader.get_next_task()
    if not next_task:
        print(json.dumps({"status": "no_tasks"}))
        return
    
    proposal = engine.classify_task(next_task)
    proposal["title"] = next_task.get("title")
    print(json.dumps(proposal, indent=2))

def main():
    if "--propose-next" in sys.argv:
        propose_next()
    else:
        print("Usage: pleiades-factory-operator.py --propose-next")
        sys.exit(1)

if __name__ == "__main__":
    main()
