#!/usr/bin/env bash
# Developing Mind — Autonomous Reviewer
# Role: Substitutes operator input with a dual Codex Judge + OpenCode Review cycle.
# Arxiv Anchor: 2604.24579 (Prop 1: Analytic Reliability) - Autonomous Verification

REPRO_DIR="./developing-mind-reproduction"
SCRIPTS_DIR="$REPRO_DIR/scripts"

echo "🤖 Initiating Autonomous Review Sequence (Operator Substitution Mode)..."

# 1. OpenCode Review (GGA Standards Check)
echo "🔍 Stage 1: OpenCode Review (Gentleman Guardian Angel)..."
bash "$SCRIPTS_DIR/substrate-sync.sh" --review-only
GGA_EXIT=$?

# 2. Codex Judge (Logic & Health Audit)
echo "⚖️ Stage 2: Codex Judge (Functional Audit)..."
# Force a judge run in the LAMP stack
echo "2026-06-07 2" > /substrate/mind/lamp/state/cron-run.state
bash /substrate/mind/lamp/ai-scaffold/cron-run.sh
JUDGE_EXIT=$?

# 3. Decision Logic
if [ $GGA_EXIT -eq 0 ] && [ $JUDGE_EXIT -eq 0 ]; then
    echo "✅ AUTONOMOUS VERIFICATION PASSED. Both Auditors approved the changes."
    exit 0
else
    echo "🚨 AUTONOMOUS VERIFICATION FAILED. Manual override or Refinement required."
    echo "OpenCode Status: $GGA_EXIT | Codex Judge Status: $JUDGE_EXIT"
    exit 1
fi
