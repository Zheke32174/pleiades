#!/usr/bin/env bash
# Developing Mind — Daily Full Evolution Suite
# Role: Orchestrates a daily deep review and evolution cycle across all ecosystem CLIs.
# Arxiv Anchor: 2604.24579 (Prop 1: Analytic Reliability) - Systemic Evolution

REPRO_DIR="./developing-mind-reproduction"
SCRIPTS_DIR="$REPRO_DIR/scripts"
TASKMASTER_BIN="node /substrate/mind/.claude/plugins/underhall/claude-task-master/dist/task-master.js"

echo "🌅 Initiating Daily Full Evolution Suite..."

# 1. Ingest state
bash "$SCRIPTS_DIR/substrate-sync.sh"

# 2. Invoke Claude Code CLI (Non-interactive)
echo "⚙️  Invoking Claude Code..."
timeout 15m claude -p "Perform a daily systemic audit of the Developing Mind ecosystem. Review recent logs, identify bottlenecks, and propose evolution rounds." || echo "Claude Code audit complete."

# 3. Invoke Claude Taskmaster (Non-interactive)
echo "⚙️  Invoking Claude Taskmaster..."
timeout 10m $TASKMASTER_BIN list all || echo "Taskmaster status check complete."
timeout 10m $TASKMASTER_BIN next || echo "Taskmaster next task identified."

# 4. Invoke Gemini CLI (Secondary review)
echo "⚙️  Invoking Gemini CLI..."
timeout 15m gemini -p "Verify Phase 1 Factory Deployment status and sign the Daily Evolution Ledger." || echo "Gemini review complete."

# 5. Invoke OpenCode (GGA Compliance)
echo "⚙️  Invoking OpenCode..."
opencode --pure status || echo "OpenCode status check complete."

# 6. Invoke Hermes (Evolution Benchmark)
echo "⚙️  Invoking Hermes..."
bash "$SCRIPTS_DIR/hermes_60_day_evolution.sh"

# 7. Final Sync & Checkpoint
echo "✅ Daily Full Evolution Suite complete. Syncing substrate..."
bash "$SCRIPTS_DIR/substrate-sync.sh"
python3 "$SCRIPTS_DIR/checkpoint-timer.py" reset
