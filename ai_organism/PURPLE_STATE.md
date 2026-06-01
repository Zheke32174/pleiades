# AI Organism — PURPLE_STATE.md

## Status: Integrated (2026-05-30)

## Components Installed

| Component | Location | Status |
|-----------|----------|--------|
| continual_harness | /workspaces/gentoo/continual_harness/ | ✅ Full (CH + MUSE + Hermes) |
| CodexSaver MCP | pip + ~/.claude.json mcpServers | ✅ Live |
| MemOS | pip MemoryOS-2.0.17 + ~/.claude.json mcpServers | ✅ Live |
| mirage-ai | pip 0.0.1 | ✅ Installed |
| agent-rules-books | /workspaces/gentoo/tools/agent-rules-books/ | ✅ Skills copied |
| chorus | /workspaces/gentoo/tools/chorus/ (npm installed) | ⏳ Build pending |

## Claude Skills Added

- `arb-clean-code` — Clean Code mini rules
- `arb-refactoring` — Refactoring mini rules  
- `arb-designing-data-intensive-applications` — DDIA mini rules
- `arb-domain-driven-design` — DDD mini rules

## MCP Servers (in ~/.claude.json)

- `ghost` — PostgreSQL managed DB
- `jcodemunch-mcp` — Code intelligence
- `piia-engram` — Cross-session memory
- `codegraph` — Code graph
- `codexsaver` — Cost-aware task delegation ← NEW
- `memos` — MemOS semantic memory ← NEW

## AI Organism Files

```
/workspaces/gentoo/ai_organism/
  cli_router.py      — Routes tasks: high-risk→claude-code, low-risk→codex via CodexSaver
  memos_bridge.py    — MemOS wrapper for HarnessState.M semantic retrieval
  memos_data/        — MemOS persistence dir (created at runtime)
```

## Integration Architecture

```
Factory run N
├─ ContinualHarness inner loop: agent acts each step
│   └─ Context: ContextDAG L1/L2 compression <50k tokens
└─ every F=50 steps → Refiner (2605.09998)
     ├─ Pass i:   rewrite system prompt p
     ├─ Pass ii:  CRUD sub-agents G
     ├─ Pass iii: MUSE skill lifecycle (2605.27366)
     │             spec→create→eval→pass/register OR fail/patch
     └─ Pass iv:  CRUD memory M → MEMOSBridge for semantic retrieval

Between runs: Hermes GEPA offline skill optimization → bootstrap next run

Task routing: cli_router.py
  security/prod → claude-code (no delegation)
  arch/design   → claude-code + DDD/DDIA rules
  refactor/test → codex via CodexSaver + clean-code/refactoring rules

Cost delegation: CodexSaver MCP delegate_task
Rules injection: agent-rules-books mini files via cli_router.rules_text()
```

## Separation Boundary (CRITICAL)

AI Organism = continual_harness/ + ai_organism/ + factory integration
Polyglot Zero Operator = /workspaces/gentoo/polyglot-testing/ (OWN git repo, OWN scope)
NEVER mix these two.

## Recently Changed

- 2026-05-30: CodexSaver pip install + MCP wired
- 2026-05-30: MemOS pip install + MCP wired + memos_bridge.py
- 2026-05-30: mirage-ai pip installed (sandbox backend for MUSE SkillEvaluator)
- 2026-05-30: arb-* skills created in ~/.claude/skills/
- 2026-05-30: cli_router.py — cost-aware CLI routing with rules injection
- 2026-05-30: chorus cloned + npm install (MCP peer review gate)

## Known Issues

- MemOS warns about missing NACOS_SERVER_ADDR — cosmetic, fallback works
- mirage-ai 0.0.1 has fastapi version conflict — functional for local use
- chorus dist/ build still running (npm run build)
- AIS-OS / WRITING.md / goalbuddy not yet in tools/ (secondary priority)
