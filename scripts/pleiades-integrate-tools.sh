#!/usr/bin/env bash
source "${PLEIADES_TERMUX_LIB:-}" 2>/dev/null || true
# pleiades-integrate-tools.sh — Wire all registered tools into every agent CLI
# Based on: agents-best-practices framework
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TOOLS_DIR="$PROJECT_ROOT/tools"
MANIFEST="$PROJECT_ROOT/tool-manifest.json"

# CLI config paths
CODEX_SKILLS="${CODEX_HOME:-$HOME/.codex}/skills"
CODEX_RULES="${CODEX_HOME:-$HOME/.codex}/rules"
CLAUDE_SKILLS="${CLAUDE_HOME:-$HOME/.claude}/skills"
GEMINI_SKILLS="${GEMINI_HOME:-$HOME/.gemini}/skills"

echo "=== Pleiades Tool Integration (agents-best-practices framework) ==="

# Step 1: Create symlinks to tools for each CLI
register_tool() {
    local tool_name="$1"
    local tool_path="$2"
    local tool_category="$3"
    
    # Create a symlink in each CLI's skills dir for discoverability
    for target in "$CODEX_SKILLS" "$CLAUDE_SKILLS" "$GEMINI_SKILLS"; do
        mkdir -p "$target"
        ln -sf "$tool_path" "$target/$tool_name" 2>/dev/null
    done
    echo "  [+] $tool_name ($tool_category)"
}

# Step 2: Generate AGENTS.md sections for each tool
generate_tool_doc() {
    local tool_name="$1"
    local tool_path="$2"
    local category="$3"
    
    readme="$tool_path/README.md"
    if [[ -f "$readme" ]]; then
        local desc=$(head -10 "$readme" | grep -E '^#[^#]|^<h1|description' | head -3)
        echo "    - **$tool_name** ($category): $desc"
    else
        echo "    - **$tool_name** ($category): (no README)"
    fi
}

echo ""
echo "=== Registered Tools ==="
echo ""
echo "## Tool Inventory"
echo ""

# Process all tools
if command -v jq &>/dev/null && [[ -f "$MANIFEST" ]]; then
    for tool in $(jq -r '.tools | keys[]' "$MANIFEST"); do
        category=$(jq -r ".tools["$tool"].category" "$MANIFEST")
        path=$(jq -r ".tools["$tool"].path" "$MANIFEST")
        register_tool "$tool" "$path" "$category"
    done
else
    for tool_dir in "$TOOLS_DIR"/*/; do
        tool=$(basename "$tool_dir")
        register_tool "$tool" "$tool_dir" "general"
    done
fi

# Step 3: Sync AGENTS.md with tool inventory
echo ""
echo "=== Syncing AGENTS.md ==="
echo "Run: pleiades-factory-tools.sh status"
echo ""
echo "=== Done ==="
echo "Tools are now registered in:"
echo "  - ~/.codex/skills/"
echo "  - ~/.claude/skills/"
echo "  - ~/.gemini/skills/"
