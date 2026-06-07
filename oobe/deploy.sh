#!/usr/bin/env bash
# Pleiades — OOBE Deployment Agent Script
# Role: Bootstraps the Developing Mind ecosystem on a new system.
# Arxiv Anchor: 2511.10621 (Section 3.1) - Autonomous Deployment

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  PLEIADES — DEVELOPING MIND OOBE DEPLOYMENT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Environment Check
echo "🔍 Checking environment..."
if ! command -v wsl.exe &>/dev/null && ! [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "❌ Error: This framework requires WSL2 or Linux."
    exit 1
fi

# 2. Setup Substrate
echo "📂 Initializing local substrate..."
BASE_DIR=$(pwd)
mkdir -p "$BASE_DIR/substrate/scripts" "$BASE_DIR/substrate/tests" "$BASE_DIR/substrate/src" "$BASE_DIR/logs"
cp "$BASE_DIR/scripts/"* "$BASE_DIR/substrate/scripts/"
cp "$BASE_DIR/templates/"* "$BASE_DIR/substrate/"

# 3. Configure Cron (Non-interactive)
echo "⏰ Configuring governance and evolution crontabs..."
(crontab -l 2>/dev/null; cat << CRON
0 7 * * * /usr/bin/python3 $BASE_DIR/substrate/scripts/daily_governance.py >> $BASE_DIR/logs/governance.log 2>&1
0 8 * * * /usr/bin/bash $BASE_DIR/substrate/scripts/daily_full_evolution_suite.sh >> $BASE_DIR/logs/deep_evolution.log 2>&1
*/15 * * * * /usr/bin/bash $BASE_DIR/substrate/scripts/hivemind_governor.sh >> $BASE_DIR/logs/hivemind.log 2>&1
CRON
) | crontab -

# 4. Agent Instructions
echo "🧠 Finalizing agent instructions..."
echo "Please instruct your Gemini-CLI to ingest $BASE_DIR/substrate/GEMINI.md"

echo "✅ OOBE Deployment Complete. Ecosystem is now autonomous."
