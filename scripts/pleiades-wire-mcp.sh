#!/bin/bash
# pleiades-wire-mcp.sh — Wire shared MCP config into all agent CLIs
set -euo pipefail

MCP_SOURCE="/workspaces/gentoo/pleiades-mcp-config.json"
echo "=== Wiring Pleiades MCP across all CLIs ==="

# Each CLI has a different config location and format
# We write the servers section into each

write_claude_config() {
    local config_file="${HOME}/.claude/settings.json"
    mkdir -p "$(dirname "$config_file")"
    if [[ -f "$config_file" ]]; then
        # Merge MCP servers into existing config
        python3 -c "
import json
with open('${config_file}') as f: config = json.load(f)
with open('${MCP_SOURCE}') as f: mcp = json.load(f)
config.setdefault('mcpServers', {}).update(mcp['mcpServers'])
with open('${config_file}', 'w') as f: json.dump(config, f, indent=2)
print('Claude: merged MCP servers')
"
    else
        cp "$MCP_SOURCE" "$config_file"
        echo "Claude: created config"
    fi
}

write_codex_config() {
    local config_file="${HOME}/.codex/settings.json"
    mkdir -p "$(dirname "$config_file")"
    if [[ -f "$config_file" ]]; then
        python3 -c "
import json
with open('${config_file}') as f: config = json.load(f)
with open('${MCP_SOURCE}') as f: mcp = json.load(f)
config.setdefault('mcpServers', {}).update(mcp['mcpServers'])
with open('${config_file}', 'w') as f: json.dump(config, f, indent=2)
print('Codex: merged MCP servers')
"
    else
        python3 -c "
import json
with open('${MCP_SOURCE}') as f: mcp = json.load(f)
with open('${config_file}', 'w') as f: json.dump({'mcpServers': mcp['mcpServers']}, f, indent=2)
print('Codex: created config')
"
    fi
}

write_gemini_config() {
    local config_file="${HOME}/.gemini/settings.json"
    mkdir -p "$(dirname "$config_file")"
    if [[ -f "$config_file" ]]; then
        python3 -c "
import json
with open('${config_file}') as f: config = json.load(f)
with open('${MCP_SOURCE}') as f: mcp = json.load(f)
config.setdefault('mcpServers', {}).update(mcp['mcpServers'])
with open('${config_file}', 'w') as f: json.dump(config, f, indent=2)
print('Gemini: merged MCP servers')
"
    else
        cp "$MCP_SOURCE" "$config_file"
        echo "Gemini: created config"
    fi
}

write_claude_config
write_codex_config
write_gemini_config
echo ""
echo "=== MCP wiring complete ==="
