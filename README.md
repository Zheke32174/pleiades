# pleiades

Pleiades is a WSL2/Gentoo `systemd-nspawn` pleiades-team autonomous agent suite. Five polyglot agents (Maia, Electra, Taygete, Alcyone, Celaeno) run inside the container, providing mutual persistence, honeypot environments, credential monitoring, recon, and watchdog/pleiades-rebirth.

## Companion repositories

| Repo | Purpose |
|---|---|
| **[Zheke32174/pleiades](https://github.com/Zheke32174/pleiades)** | This repo — host scripts, task master, toolchain catalog |
| **[Zheke32174/pleiades-container](https://github.com/Zheke32174/pleiades-container)** | Gentoo nspawn rootfs — the container image running the agent stack |
| **[Zheke32174/pleiades-factory-stack](https://github.com/Zheke32174/pleiades-factory-stack)** | Factory tools, AI/LLM stack, cross-ISA toolchain |
| **[Zheke32174/pleiades-evidence](https://github.com/Zheke32174/pleiades-evidence)** | Private — secured evidence archive (auto-pushed by selfdestruct) |

**Rehydration:** `dead_drop/signal.json` in this repo is the dead drop — writing `{"action":"redeploy"}` triggers the ESP capsule to pull and rebuild.

## Quick start

```bash
gentoo-up                    # start container
gentoo-shell                 # enter container

# Install auto-start at OS boot (WSL or bare metal)
sudo bash root.x86_64/scripts/install-boot-persistence.sh

# Emergency: preserve evidence, wipe traces, signal redeploy
sudo bash root.x86_64/scripts/pleiades-selfdestruct.sh --redeploy
```

## Agent suite (inside container)

| Script | Agent | Role |
|---|---|---|
| `Maia.sh` | Maia | Overseer, EFI/ESP persistence, GitHub rehydration |
| `Electra.sh` | Electra | Fake env (`imtherealsparticus`), `sysmon-daemon` pleiades-swarm |
| `Taygete.sh` | Taygete | Credential monitor, BGP watch |
| `Alcyone.sh` | Alcyone | Recon, host bridge capability reporting |
| `Celaeno.sh` | Celaeno | Watchdog, process guardian, pleiades-rebirth |

Read `PLEIADES_STATE.md` and `AGENTS.md` before making changes.

- `gentoo-up` starts the Gentoo `systemd-nspawn` container.
- `gentoo-shell` enters the running container with `nsenter`.

Backup before every edit: `cp file file.bak.$(date +%s)`

---

## Task Progress

**Last synced:** 2026-06-01 · **Branch:** pleiades/research-integration

`░░░░░░░░░░░░░░░░░░░░` 0% complete (0 / 18 tasks done)

| Metric | Count |
|---|---|
| Total tasks | 18 |
| Total subtasks | 65 |
| Done | 0 |
| In Progress | 0 |
| Pending | 18 |

---

## Tasks by Area

### Compiler & Toolchain Catalog

- ⏳ 🟡 **#9** Build machine-readable compiler/toolchain catalog *(complexity 4)*
  - ⬜ 1. Define JSON schema and create catalog template structure
  - ⬜ 2. Implement GitHub API fetcher with rate limiting and web scraping fallback
  - ⬜ 3. Populate catalog with metadata validation and visibility checks
- ⏳ 🔴 **#10** Extend omnipkg for compiler/toolchain binary staging *(complexity 5 · deps: #9)*
  - ⬜ 1. Add install-toolchain subcommand with tarball fetch and checksum verification
  - ⬜ 2. Implement Zig handler (ziglang.org download, /opt/zig extraction, symlinks)
  - ⬜ 3. Implement Nim handler (choosenim vs tarball decision logic)
  - ⬜ 4. Implement V handler and finalize toolchains.json metadata database
- ⏳ 🟡 **#11** Extend alien-bsd for Nim nimble and V vpkg packages *(complexity 5 · deps: #10)*
  - ⬜ 1. Implement Nim .nimble package parser and ecosystem detection
  - ⬜ 2. Implement V vpkg package parser with v.mod support
  - ⬜ 3. Integrate Nim/V parsers with alien-bsd conversion pipeline and validate end-to-end
- ⏳ 🟢 **#12** Integrate Zheke32174 repos into purple team build pipeline *(complexity 4 · deps: #11)*
  - ⬜ 1. Clone all four Zheke32174 repos and verify access
  - ⬜ 2. Three-way merge alien fork with local alien-bsd
  - ⬜ 3. Analyze scandroid/Tracendroid/underlode and create integration specs
  - ⬜ 4. Update taskmaster docs and register tools in capability registry
- ⏳ 🟡 **#13** Evaluate and stage AI coding agents (Aider, OpenHands) *(complexity 5 · deps: #9)*
  - ⬜ 1. Install Aider and create purplectl plugin stub
  - ⬜ 2. Verify OpenHands installation and create integration wrapper
  - ⬜ 3. Register both tools as pleiades-swarm capabilities with policy gates
  - ⬜ 4. Create configuration files and update nlspec documentation

### RE / Binary Analysis & AI Infra

- ⏳ 🔴 **#14** Build binary decompilation + LLM refinement pipeline *(complexity 9)*
  - ⬜ 1. Create pleiades-re.sh script skeleton with argument parsing
  - ⬜ 2. Implement Stage 1 Ghidra/radare2 decompilation with tool detection
  - ⬜ 3. Implement Stage 2 LLM refinement integration (depends on #18)
  - ⬜ 4. Implement Stage 3 type recovery heuristics
  - ⬜ 5. Implement Stage 4 report generation with markdown formatting
  - ⬜ 6. Integration with pleiades-forensic-scanner.sh for coordinated analysis
- ⏳ 🟡 **#15** Set up cross-ISA translation layer (QEMU user-mode + Box64) *(complexity 5)*
  - ⬜ 1. Install and configure QEMU user-mode with binfmt_misc handlers
  - ⬜ 2. Build and install Box64 from source for x86-to-ARM translation
  - ⬜ 3. Document cross-ISA patterns and integrate with Asterope.sh
- ⏳ 🔴 **#16** Implement vulnerability discovery + fuzzing loop *(complexity 5 · deps: #14)*
  - ⬜ 1. Implement static analysis and input vector identification
  - ⬜ 2. Implement LLM harness generation and AFL++ fuzzing execution
  - ⬜ 3. Implement crash validation and LLM patch proposal generation
- ⏳ 🔴 **#18** Deploy quantized local LLM inference stack *(complexity 8)*
  - ⬜ 1. Build llama.cpp with CUDA detection and optimal compile flags
  - ⬜ 2. Download and validate 4-bit quantized model from HuggingFace
  - ⬜ 3. Create pleiades-llm wrapper with context/GPU/memory tuning
  - ⬜ 4. Integrate pleiades-llm with pleiades-re.sh and pleiades-fuzz.sh via stdin/stdout
  - ⬜ 5. Add systemd resource limits and performance benchmarking

### Security Package Deployment

- ⏳ 🔴 **#17** Deploy all 32 verified Gentoo security atoms *(complexity 5 · deps: #10)*
  - ⬜ 1. Create security-baseline.json manifest with all 32 Gentoo atoms
  - ⬜ 2. Implement omnipkg security-baseline install subcommand
  - ⬜ 3. Create purplectl verify-tools validation script
- ⏳ 🟡 **#19** Create distro-agnostic security package install scripts *(complexity 6 · deps: #17)*
  - ⬜ 1. Implement Bedrock/stratum detection and distro identification logic
  - ⬜ 2. Create comprehensive distro-map.json with 32 security tool mappings
  - ⬜ 3. Implement omnipkg install-cross dispatcher with package manager abstraction
  - ⬜ 4. Add error handling, offline mode support, and fallback mechanisms
- ⏳ 🟡 **#20** Wire security tools into Pleiades Team capability registry *(complexity 5 · deps: #17)*
  - ⬜ 1. Create security tool catalog and register 32 security tools in capability registry
  - ⬜ 2. Implement purplectl list-capabilities with domain-grouped pretty-print
  - ⬜ 3. Create purplectl domain-specific tool invocation subcommands with policy enforcement
- ⏳ 🟢 **#21** Create offline security package bundle for air-gapped deployment *(complexity 3 · deps: #17)*
  - ⬜ 1. Implement package collection from binpkg cache with manifest generation
  - ⬜ 2. Create install-offline.sh script with verification and container deployment logic

### MCP Converter Pipeline

- ⏳ 🟡 **#22** Implement repo2mcp pipeline (GitHub → context packer → MCP server) *(complexity 7 · deps: #13)*
  - ⬜ 1. Create pleiades-mcp-converters.sh scaffold and install dependencies
  - ⬜ 2. Implement repo cloning and context packing stage
  - ⬜ 3. Implement Aider integration for FastMCP generation with templating
  - ⬜ 4. Create FastMCP server output with Python/TypeScript support
  - ⬜ 5. Add purplectl convert repo2mcp command and integration testing
- ⏳ 🟡 **#23** Implement paper2mcp pipeline (arXiv → Paper2Code → MCP tool) *(complexity 5 · deps: #13)*
  - ⬜ 1. Set up Paper2Code integration and arXiv PDF fetching
  - ⬜ 2. Implement Paper2Code code generation pipeline
  - ⬜ 3. Wrap generated code as MCP server and integrate with purplectl
- ⏳ 🟡 **#24** Implement openapi2mcp converter (OpenAPI spec → MCP server) *(complexity 6 · deps: #13)*
  - ⬜ 1. Install openapi-mcp-codegen and extend pleiades-mcp-converters.sh
  - ⬜ 2. Implement OpenAPI spec parsing for endpoints and parameters
  - ⬜ 3. Generate MCP tools with authentication handling for OpenAPI 3.0/3.1
  - ⬜ 4. Create purplectl convert openapi2mcp command and test with public APIs

### Cross-Bundle / Disaster Recovery

- ⏳ 🟢 **#25** Add WASM runtime stratum to Asterope.sh BSD layer *(complexity 5 · deps: #10)*
  - ⬜ 1. Install Wasmtime and jco tooling for WASM execution
  - ⬜ 2. Implement bootstrap_wasm_runtime() function and register capability
  - ⬜ 3. Add purplectl quantum wasm-run command integration
- ⏳ 🔴 **#26** Disaster recovery test: full purple team rebuild from scratch *(complexity 5 · deps: #10, #17, #20, #25)*
  - ⬜ 1. Pre-flight safety checks and backup creation
  - ⬜ 2. Extract stage3 tarball and bootstrap base purple team system
  - ⬜ 3. Deploy security baseline and toolchains, validate DR success

---

## Critical Path

```
#9 → #10 → #17 → #20 → #26   (5 tasks — security deployment track)
#18 → #14 → #16               (3 tasks — RE / LLM track)
#9  → #13 → #22/#23/#24       (MCP converter track)
#15                            (standalone — no deps)
```

## Ready to Start Now

| Task | Priority | Complexity |
|---|---|---|
| **#9** Build machine-readable compiler/toolchain catalog | medium | 4 |
| **#14** Build binary decompilation + LLM refinement pipeline | high | 9 |
| **#15** Set up cross-ISA translation layer (QEMU + Box64) | medium | 5 |
| **#18** Deploy quantized local LLM inference stack | high | 8 |

## Key Files

| Path | Purpose |
|---|---|
| `PLEIADES_STATE.md` | Shared agent state, known-good decisions, recent changes |
| `omnipkg` | Universal package ecosystem → Gentoo container pipeline |
| `alien-bsd` | BSD/multi-ecosystem package converter (deb + Gentoo output) |
| `root.x86_64/scripts/Asterope.sh` | BSD compatibility layer with WASM stratum |
| `root.x86_64/scripts/Taygete.sh` | Cross-distro package manager + capability registry |
| `root.x86_64/scripts/Alcyone.sh` | Adaptive builder and environment orchestrator |
| `.taskmaster/tasks/tasks.json` | Full task graph with 65 subtasks |
| `.taskmaster/reports/task-complexity-report.json` | Complexity scores and expansion prompts |
| `.taskmaster/docs/research_prd_2026-05-31.md` | Source PRD from 4 research bundles |

---

## Credits & Third-Party Components

This project incorporates and builds upon the following open-source projects and technologies:

### Core Infrastructure
- **Gentoo Linux** — Stage 3 base system ([gentoo.org](https://gentoo.org)) — GPL v2
- **systemd** — System and service manager ([systemd.io](https://systemd.io)) — LGPL v2.1+
- **s6-overlay** — Process supervision suite ([skarnet.org](https://skarnet.org/software/s6/)) — ISC License
- **Bedrock Linux** — Multi-distribution strata system ([bedrocklinux.org](https://bedrocklinux.org)) — GPL v2
- **systemd-nspawn** — Lightweight namespace containers — LGPL v2.1+
- **WSL2** — Windows Subsystem for Linux ([learn.microsoft.com/wsl](https://learn.microsoft.com/en-us/windows/wsl/)) — Microsoft ToS

### Agent & AI Frameworks
- **Hermes Agent** — AI agent framework ([github.com/NousResearch/hermes](https://github.com/NousResearch/hermes)) — MIT
- **Claude Code** — CLI coding agent ([docs.anthropic.com](https://docs.anthropic.com/en/docs/claude-code)) — Anthropic ToS
- **Codex CLI** — CLI coding agent ([github.com/openai/codex](https://github.com/openai/codex)) — Apache 2.0
- **Gemini CLI** — CLI coding agent ([google-gemini.github.io](https://google-gemini.github.io)) — Google ToS
- **OpenCode** — CLI coding agent ([github.com/samp-labs/opencode](https://github.com/samp-labs/opencode)) — Apache 2.0

### Emulation & Cross-ISA
- **QEMU** — Machine emulator ([qemu.org](https://qemu.org)) — GPL v2
- **Box64** — Linux x86_64 emulator for ARM64 ([github.com/ptitSeb/box64](https://github.com/ptitSeb/box64)) — MIT
- **FEX** — Fast x86 emulator for ARM ([github.com/FEX-Emu/FEX](https://github.com/FEX-Emu/FEX)) — MIT

### Research & Tooling
- **arXiv** — Open access scholarly articles ([arxiv.org](https://arxiv.org)) — Cornell University
- **Weights & Biases** — ML experiment tracking ([wandb.ai](https://wandb.ai)) — MIT
- **PyGount** — Code analysis and LOC counting ([github.com/roskakori/pygount](https://github.com/roskakori/pygount)) — BSD
- **TaskMaster** — AI-driven task orchestration framework — Part of this project

### Development Resources
- **[Underhall](https://github.com/Zheke32174/underhall)** — Original Arch nspawn install layer (companion project)
- **[Undercity](https://github.com/Zheke32174/undercity)** — Backup/restore tooling (companion project)

### License
The Pleiades-sourced content in this repository is provided under the MIT License unless otherwise noted. Each integrated third-party component is subject to its own license as referenced above.