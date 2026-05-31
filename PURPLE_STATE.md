# PURPLE_STATE.md — Pleiades Purple Team Suite

## Project Purpose
Pleiades is the SofiaX Purple Team Polyglot Suite — an Ouroboros mutual-persistence security framework. It provides container-resident defense and host protection for the Gentoo/Bedrock WSL environment.

## Current Known-Good State
- Repository structure: core/, modules/, docs/, container/
- CI: active with shell syntax check
- DevContainer: NEW — codespaces compatible setup

## Deliberate Design Decisions
- Go-based core for performance-critical components
- Bash scripts for orchestration and glue logic
- Ouroboros event bus (/run/purple/ouroboros_fifo) as the central integration point

## Recently Changed
- Added .devcontainer/devcontainer.json (2026-05-31)
- Added .devcontainer/setup.sh (2026-05-31)
- Upgraded .github/workflows/ci.yml (2026-05-31)

## Known Issues
- DevContainer config not yet tested end-to-end
- No integration tests in CI

## Related Ecosystem Repos
- Zheke32174/underhall — container infrastructure (has devcontainer + CI)
- Zheke32174/undercity — backup/archive
- Zheke32174/underforge — skill engine
