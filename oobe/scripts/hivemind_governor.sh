#!/usr/bin/env bash
# Developing Mind — Hivemind Governor
# Role: Orchestrates the multi-CLI ecosystem (Copilot, OpenCode, Hermes, Gemini, Claude, Codex).
# Arxiv Anchor: 2604.24579 (Prop 1: Analytic Reliability) - Ecosystem Governance & Quota Management

STATE_FILE="./developing-mind-reproduction/scripts/quota_state.txt"
REPRO_DIR="./developing-mind-reproduction"

echo "Checking Hivemind Quota State..."

if [ -f "$STATE_FILE" ]; then
    QUOTA_TIME=$(cat "$STATE_FILE")
    CURRENT_TIME=$(date +%s)
    DIFF=$((CURRENT_TIME - QUOTA_TIME))
    if [ "$DIFF" -lt 43200 ]; then
        HOURS_LEFT=$(( (43200 - DIFF) / 3600 ))
        echo "Quota cooldown active. $HOURS_LEFT hours remaining until Hivemind re-awakens."
        exit 0
    else
        echo "12-Hour Quota cooldown expired. Resuming continuous operations."
        rm -f "$STATE_FILE"
    fi
fi

cd "$REPRO_DIR"

echo "Amnesia Prevention: Ingesting the most recent state..."
bash scripts/substrate-sync.sh

echo "Initiating Hivemind Orchestration Loop..."

run_cli() {
    local CLI_NAME="$1"
    shift
    echo "Invoking $CLI_NAME..."
    
    local OUTPUT
    OUTPUT=$(timeout 10m "$CLI_NAME" "$@" 2>&1)
    
    if echo "$OUTPUT" | grep -iE "429|too many requests|quota exceeded|exhausted|rate limit"; then
        echo "$CLI_NAME quota exceeded! Triggering 12-hour ecosystem hibernation."
        date +%s > "$STATE_FILE"
        exit 1
    fi
    echo "$CLI_NAME execution verified."
}

# 1. Hermes: Evolution Validation (60-day rule check)
run_cli bash scripts/hermes_60_day_evolution.sh

# 2. Codex: Governance & Judging (7:00 AM rules)
run_cli bash scripts/daily_governance.py

# 3. OpenCode: Substrate Quality Review
run_cli opencode --pure --print-logs status

# 4. Claude Code: Deep Memory Synthesis
run_cli bash ./scripts/fetch_claude_memory.sh

# 4.5 Conductor Suite: Ecosystem Coherence
run_cli bash scripts/conductor_suite_orchestrator.sh

# 5. Gemini CLI: The Primary Ralph Automation Loop
echo "Triggering Gemini CLI to progress the 100-Task Ralph Loop..."
OUTPUT=$(timeout 30m gemini -p "continue ralph loop from state" 2>&1)
if echo "$OUTPUT" | grep -iE "429|too many requests|quota exceeded|exhausted|rate limit"; then
    echo "Gemini CLI quota exceeded! Triggering 12-hour ecosystem hibernation."
    date +%s > "$STATE_FILE"
    exit 1
fi

echo "Hivemind multi-framework cycle complete. Awaiting next cron execution."
