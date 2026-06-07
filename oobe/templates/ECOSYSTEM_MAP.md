# Ecosystem Components Map

This document tracks all currently active components, services, and workers across the multi-framework ecosystem.

## 1. Host Layer (Windows 11)
- **Pleiades-WSL-Background:** Scheduled Task (Starts WSL and the Gentoo container at logon).
- **WSL-Health-Check-9AM:** Scheduled Task (9:00 AM daily health check and recovery script for WSL).
- **Gemini-Heartbeat-AM/PM:** Scheduled Tasks (12:00 AM/PM interactive Gemini wake-up sequences).

## 2. Substrate Layer (WSL2 / Gentoo nspawn)
- **Underhall Substrate:** Gentoo-based multi-strata container.
- **Pleiades Swarm:** Defensive and monitoring suite.
- **Subconscious Daemon:** Monitors disk (15GB rule), RAM, and maintains the 30-minute checkpoint.
- **Hivemind Governor:** Orchestrates Copilot, OpenCode, Hermes, Gemini, Claude, and Codex with quota-aware 12-hour hibernation.
- **Ralph Watchdog:** Ensures the Ralph loop is continuously running or self-corrects on failure.

## 3. Agents & Frameworks
- **Gemini CLI:** Primary interactive interface and task orchestrator.
- **Claude Code:** Provides Deep Memory Synthesis via `fetch_claude_memory.sh`.
- **Codex Judge:** Non-interactive critic for daily LAMP stack validation.
- **OpenCode:** Runs the Gentleman Guardian Angel (GGA) for quality reviews.
- **Hermes CLI:** Handles the 60-Day Evolution cycle against Attractor NLSpecs.
- **Open-Viking Framework:** Fully patched for local auth proxying.
- **Taskmaster:** Handles TDD and sub-task orchestration.

## 4. Governance & Verification
- **7:00 AM Daily Governance:** Analyzes logs using Markovian `TraceToChain` (Paper 2604.24579).
- **15GB Storage Guard:** Triggers automated bloat cleanup and dependency consolidation (pnpm).

## 5. Persistence
- **Git-Backed Neural Engram:** `Zheke32174/developing-mind-reproduction` GitHub repository.
- **Timestamp Ledger:** `PHASE_2_LEDGER.md` for verifiable audits.
