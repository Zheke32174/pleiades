# Arxiv Anchor: 2406.03075 (Section 3.3) - Cohesion
import os
import json

MAIL_DIR = "./swarmmail/inbox"

def get_alerts():
    alerts = []
    for f in os.listdir(MAIL_DIR):
        if f.endswith(".json"):
            with open(os.path.join(MAIL_DIR, f), "r") as alert_file:
                alerts.append(json.load(alert_file))
            os.remove(os.path.join(MAIL_DIR, f)) # Destructive read (pop)
    return alerts

if __name__ == "__main__":
    alerts = get_alerts()
    if alerts:
        print(f"--- Received {len(alerts)} Swarm Alerts ---")
        for a in alerts:
            print(f"[{a['priority'].upper()}] {a['subject']}: {a['message']}")
    else:
        print("No new alerts.")
