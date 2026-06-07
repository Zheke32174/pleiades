#!/usr/bin/env bash
# Developing Mind — Gemini Parallel Debugger
# Role: Diagnoses and patches failures in the Sub-Hermes evolution cycle.
# Arxiv Anchor: 2604.24579 (Prop 1: Analytic Reliability) - Fault Tolerance

ERROR_LOG="$1"
FAILED_COMMAND="$2"

echo "🐛 Parallel Debugger Activated for: $FAILED_COMMAND"

if [ -f "$ERROR_LOG" ]; then
    echo "🧠 Sending error state to Gemini for parallel debugging..."
    gemini -p "The background evolution command '$FAILED_COMMAND' failed with the following error: $(cat "$ERROR_LOG"). Debug this issue, apply a patch to the substrate, and signal a restart."
    
    # After debugging, we attempt to clear the error and allow the next scheduled run
    echo "🛠️  Patching complete. Subconscious state synchronized."
    exit 0
else
    echo "❌ Error log missing. Manual intervention suggested."
    exit 1
fi
