# Arxiv Anchor: 2604.24579 (Prop 1: Analytic Reliability) - Time-based Checkpoints
import json
import os
from datetime import datetime, timedelta
import sys

STATE_FILE = "./developing-mind-reproduction/scripts/checkpoint_state.json"

def check_timer():
    if not os.path.exists(STATE_FILE):
        return True
    with open(STATE_FILE, "r") as f:
        state = json.load(f)
    last_sync = datetime.fromisoformat(state["last_sync"])
    return (datetime.now() - last_sync) > timedelta(minutes=30)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        with open(STATE_FILE, "w") as f:
            json.dump({"last_sync": datetime.now().isoformat()}, f)
    else:
        sys.exit(1 if check_timer() else 0)
