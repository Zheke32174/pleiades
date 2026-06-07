#!/usr/bin/env python3
# Developing Mind — Secretary Service Worker
# Role: Performs daily brief monitor sweeps and aggregates security data for the Sub-Governor.
# Arxiv Anchor: 2604.24579 (Prop 1: Analytic Reliability) - Data Aggregation

import os
import json
import subprocess
from datetime import datetime

STAGING_DIR = "./lamp/logs/secretary_staging"
os.makedirs(STAGING_DIR, exist_ok=True)

def daily_sweep():
    print("🧹 Secretary Service Worker: Initiating daily monitor sweep...")
    report = {
        "timestamp": datetime.now().isoformat(),
        "disk": subprocess.getoutput("df -h /"),
        "processes": subprocess.getoutput("ps aux --sort=-%mem | head -n 10"),
        "security_events": subprocess.getoutput("grep 'sudo:' /var/log/auth.log | tail -n 5 2>/dev/null || echo 'No events'"),
        "mcp_health": subprocess.getoutput("gemini mcp list 2>/dev/null || echo 'MCP status check failed'")
    }
    
    file_name = f"sweep_{datetime.now().strftime('%Y%m%d')}.json"
    with open(os.path.join(STAGING_DIR, file_name), "w") as f:
        json.dump(report, f, indent=2)
    print(f"✅ Daily sweep collected: {file_name}")

if __name__ == "__main__":
    daily_sweep()
