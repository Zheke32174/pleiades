# Pleiades Tool Framework
# Based on: agents-best-practices (github.com/DenisSergeevitch/agents-best-practices)
# Last updated: 2026-06-01

## Purpose
Standardize all third-party tools, arXiv implementations, and AI/agent projects
so they work identically across Claude Code, Codex CLI, Gemini CLI, and OpenCode.

## Integration Model

Each tool is registered as one or more of:
1. **MCP Server** — exposed as a tool to all agent CLIs
2. **Agent Skill** — loaded as procedural knowledge by any CLI
3. **Standalone tool** — invoked via terminal/shell from any CLI

## Tool Categories

| Category | Tools |
|----------|-------|
| Binary Analysis | angr, ddisasm, mcsema, remill, retrowrite, revng, resym, ghidra, codegraph |
| AI/Agent Frameworks | hermes-agent-self-evolution, elephant-agent, opensquilla, zerostack, continual-harness, chorus, smallcode, zerolang, openhands |
| MCP Connectors | fastapi_mcp, fastmcp, jcodemunch-mcp, openapi-mcp-codegen, piia-engram, files-sdk |
| Skill & Knowledge | CoEvoSkills, SkillGen, SkillX, CodexSaver, agent-oss, ai-memory, agent-rules-books |
| Emulation | box64, FEX, btype |
| Research | paper2code, repomix, gitingest, codeindex |
| System | WSL, LUKSbox, MemOS, Photo-agents, ShadowCat |

## MCP Servers (shared across all CLIs)

Source of truth: `/workspaces/gentoo/pleiades-mcp-config.json`

```json
{
    "mcpServers": {
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
}
```

## CLI Integration

Every tool is symlinked into:
- `~/.codex/skills/` — Codex CLI
- `~/.claude/skills/` — Claude Code
- `~/.gemini/skills/` — Gemini CLI

## Tool Manifest

Source of truth: `/workspaces/gentoo/tool-manifest.json`

This JSON manifest is machine-readable by any agent CLI. Each tool entry includes:
- Category
- Installation status
- MCP support
- Agent compatibility matrix

## Access Patterns

### For Claude Code
Load: `@agents-best-practices` in any prompt about agent architecture
Use: MCP servers auto-registered in settings.json

### For Codex CLI
Load: skills at `~/.codex/skills/`
Use: MCP servers merged into Codex settings

### For Gemini CLI
Load: skills at `~/.gemini/skills/`
Use: MCP servers merged into Gemini settings

### For OpenCode
Read: `/workspaces/gentoo/AGENTS.md` for harness rules
Use: Terminal invocation of any tool

## arXiv Paper Implementations

Each paper implementation in `tools/` should be:
1. Properly cloned from upstream (✅ all are)
2. Has install instructions (partial — some lack pyproject.toml)
3. Has README (✅ all do)
4. Has MCP config if applicable (some do: jcodemunch-mcp, fastapi_mcp, etc.)
5. Is registered in the tool manifest (✅ now is)

## Third-Party Accreditation

See [`../CREDITS.md`](../CREDITS.md) for parent-repo third-party licensing and attribution.

See [`pleiades-factory-stack/CREDITS.md`](https://github.com/Zheke32174/pleiades-factory-stack/blob/main/CREDITS.md) for factory-stack tool attribution.
