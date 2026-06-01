# Pleiades Cross-CLI MCP Configuration
# Based on: agents-best-practices framework
# Source of truth: /workspaces/gentoo/pleiades-mcp-config.json
#
# This file is loaded by ALL agent CLIs (Claude Code, Codex CLI, Gemini CLI, OpenCode)
# via symlinks in their respective config directories.

# MCP Servers registered:
{
  "jcodemunch-mcp": {
    "command": "python3",
    "args": [
      "-m",
      "jcodemunch_mcp"
    ],
    "env": {
      "JCODEMUNCH_HOME": "/workspaces/gentoo/tools/jcodemunch-mcp",
      "JCODEMUNCH_API_PORT": "37700"
    },
    "disabled": false,
    "autoApprove": []
  },
  "fastapi-mcp": {
    "command": "python3",
    "args": [
      "-m",
      "fastapi_mcp"
    ],
    "disabled": true,
    "autoApprove": []
  },
  "openapi-mcp-codegen": {
    "command": "python3",
    "args": [
      "-m",
      "openapi_mcp_codegen"
    ],
    "disabled": true,
    "autoApprove": []
  },
  "piia-engram": {
    "command": "python3",
    "args": [
      "-m",
      "piia_engram.mcp_server"
    ],
    "disabled": true,
    "autoApprove": []
  },
  "files-sdk": {
    "command": "node",
    "args": [
      "index.js"
    ],
    "disabled": true,
    "autoApprove": []
  }
}

# Instructions for each CLI:
# Claude Code:  symlink -> ~/.claude/settings.json
# Codex CLI:    symlink -> ~/.codex/settings.json
# Gemini CLI:   symlink -> ~/.gemini/settings.json
# OpenCode:     symlink -> ~/.opencode/settings.json
