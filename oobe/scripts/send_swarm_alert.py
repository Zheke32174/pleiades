# Arxiv Anchor: 2406.03075 (Section 3.3) - Cohesion
import json
import os
import sys
from datetime import datetime

MAIL_DIR = "./swarmmail/inbox"

def send_alert(subject, message, priority="normal"):
    alert = {
        "timestamp": datetime.now().isoformat(),
        "subject": subject,
        "message": message,
        "priority": priority
    }
    file_name = f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(os.path.join(MAIL_DIR, file_name), "w") as f:
        json.dump(alert, f, indent=2)
    print(f"Alert sent: {subject}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 send_swarm_alert.py <subject> <message>")
    else:
        send_alert(sys.argv[1], sys.argv[2])
