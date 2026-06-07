#!/usr/bin/env bash
# Developing Mind — subconscious-daemon.sh (Codex Judge Integrated)
# Role: Orchestrates background monitoring and invokes the Codex Judge.
# Arxiv Anchor: 2604.24579 (Prop 1: Analytic Reliability) - Background Monitoring

SCRIPTS_DIR="./developing-mind-reproduction/scripts"
LAMP_DIR="/substrate/mind/lamp"

echo "Running Subconscious Daemon checks..."

# Resource Monitors
bash "$SCRIPTS_DIR/disk_monitor.sh" || echo "Disk check flagged an issue."
bash "$SCRIPTS_DIR/ram_monitor.sh" || echo "RAM check flagged an issue."

# 30-Minute Checkpoint
python3 "$SCRIPTS_DIR/checkpoint-timer.py"
if [ $? -eq 1 ]; then
    echo "🚨 30-MINUTE CHECKPOINT REACHED. Refreshing state."
    bash "$SCRIPTS_DIR/substrate-sync.sh"
    python3 "$SCRIPTS_DIR/checkpoint-timer.py" reset
fi

# Codex Judge Integration (Trigger on demand or periodically)
# We invoke the LAMP cron runner's judge capability
echo "⚖️ Invoking Codex Judge..."
bash "$LAMP_DIR/ai-scaffold/cron-run.sh" 

echo "🐕 Running Ralph Watchdog..."
python3 "$SCRIPTS_DIR/ralph_watchdog.py"

echo "Daemon checks complete."
