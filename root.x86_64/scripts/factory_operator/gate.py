import json
import time
import sys
from pathlib import Path
from typing import Dict, Any, Optional

class ApprovalGate:
    def __init__(self, outbox_dir: Optional[Path] = None, inbox_dir: Optional[Path] = None, timeout: int = 60):
        self.outbox_dir = outbox_dir
        self.inbox_dir = inbox_dir
        self.timeout = timeout

    def request_approval(self, proposal: Dict[str, Any], mode: str = "programmatic") -> bool:
        if not proposal.get("approval_required", True):
            return True
        
        if mode == "cli":
            return self._request_cli_approval(proposal)
        else:
            return self._request_programmatic_approval(proposal)

    def _request_cli_approval(self, proposal: Dict[str, Any]) -> bool:
        print("\n--- HITL APPROVAL REQUIRED ---")
        print(f"Task: {proposal.get('title', 'Unknown')}")
        print(f"Risk Level: {proposal.get('risk_level')} ({proposal.get('label', 'UNKNOWN')})")
        print(f"Details: {proposal.get('description', 'No description provided')}")
        
        while True:
            try:
                choice = input("Approve? (y/n): ").lower().strip()
                if choice == 'y':
                    return True
                if choice == 'n':
                    return False
            except (EOFError, KeyboardInterrupt):
                return False

    def _request_programmatic_approval(self, proposal: Dict[str, Any]) -> bool:
        if not self.outbox_dir or not self.inbox_dir:
            raise ValueError("Outbox/Inbox directories must be set for programmatic mode")
            
        task_id = proposal.get("task_id")
        proposal_file = self.outbox_dir / f"proposal_{task_id}.json"
        with open(proposal_file, "w") as f:
            json.dump(proposal, f, indent=2)
        
        # Wait for approval file
        approval_file = self.inbox_dir / f"approval_{task_id}.json"
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            if approval_file.exists():
                try:
                    with open(approval_file, "r") as f:
                        response = json.load(f)
                    return response.get("approved", False)
                except json.JSONDecodeError:
                    pass
            time.sleep(1)
        
        return False
