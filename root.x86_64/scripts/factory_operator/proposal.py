import re
from typing import Dict, Any

class ProposalEngine:
    TAXONOMY = {
        "L0": {"label": "SAFE", "keywords": ["status", "read", "list", "grep", "find", "ls", "cat", "check", "verify"]},
        "L1": {"label": "BUFFERED", "keywords": ["write", "edit", "patch", "create", "update", "append"]},
        "L2": {"label": "RISKY", "keywords": ["process", "restart", "systemctl", "service", "kill", "start", "stop"]},
        "L3": {"label": "CRITICAL", "keywords": ["policy", "security", "crypto", "chmod", "chown", "root"]},
        "L4": {"label": "OUTWARD", "keywords": ["git push", "curl", "wget", "ssh", "network", "external"]}
    }
    
    def classify_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        text = (task.get("title", "") + " " + task.get("description", "") + " " + task.get("details", "")).lower()
        
        risk_level = "L0"
        # Search from highest risk to lowest
        for level in ["L4", "L3", "L2", "L1"]:
            keywords = self.TAXONOMY[level]["keywords"]
            if any(k in text for k in keywords):
                risk_level = level
                break
        
        return {
            "task_id": task.get("id"),
            "risk_level": risk_level,
            "label": self.TAXONOMY[risk_level]["label"],
            "approval_required": risk_level != "L0"
        }
