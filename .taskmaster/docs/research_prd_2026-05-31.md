# PRD: Pleiades Team Research Integration — 2026-05-31

## Overview

Four research bundles have been assembled covering: (1) compiler/toolchain/AI GitHub replacers,
(2) AI-assisted reverse engineering and cybersecurity research, (3) a verified multi-distro
security package catalog, and (4) AI converter/MCP pipeline research. This PRD captures the
implementation objectives derived from those bundles for the Gentoo/WSL Pleiades Team container.

---

## Bundle 1 — Compiler & Toolchain Catalog Integration

### Background
45 GitHub repos identified across categories: language compilers (Zig, Nim, V, Odin, Crystal,
Zen-C), JS/TS compiler platforms (SWC, Oxc, Biome, Ruff), WASM runtimes (Wasmtime, jco),
build systems (Meson, Xmake), and AI coding agents (Aider, OpenAI Codex, OpenHands). Four
user repos (Zheke32174/alien, scandroid, Tracendroid, underlode) were confirmed visible.

### Goals
1. Build a machine-readable catalog of all 45 repos with category, language, license, activity.
2. Select and stage top-tier compiler/toolchain binaries for the Gentoo container using omnipkg/alien-bsd.
3. Integrate the four Zheke32174 repos (alien fork, scandroid, Tracendroid, underlode) into
   the pleiades team build pipeline.
4. Evaluate AI coding agents (Aider, Codex CLI, OpenHands) for integration as pleiades team
   operator-assist tools.

### Acceptance Criteria
- `/workspaces/gentoo/toolchain-catalog.json` contains all 45 entries with metadata.
- `omnipkg install` successfully stages at least Zig, Nim, and V into the container.
- alien-bsd fork at `Zheke32174/alien` is pulled and merged with local alien-bsd.
- At least one AI coding agent is installable via `pleiadesctl install aider`.

---

## Bundle 2 — AI-Assisted Reverse Engineering & Cyber Pipeline

### Background
Literature map covering: LLM decompilation (LLM4Decompile, Decaf, SCRIBE), type/signature
recovery (Practical Type Inference, XTRIDE), cross-ISA translation (Elevator static binary
translation, Forklift neural lifter, EFACT, Box64/FEX/QEMU), vulnerability discovery/repair
(IRIS, QLPro, PromptFuzz, PatchIsland, HarnessAgent), and AI harness optimization (PAL,
speculative decoding, context compression, executable/verifiable agent systems).

### Goals
1. Build a staged binary analysis pipeline inside the container:
   binary → Ghidra/radare2 decompiler → LLM refinement → type recovery → output report.
2. Set up cross-ISA translation layer: QEMU user-mode for foreign binaries + Box64 for x86→ARM.
3. Implement a vulnerability discovery loop: static analysis → LLM harness generation →
   fuzzing → crash validation → patch proposal.
4. Deploy a quantized local LLM inference stack optimized for RE tasks (speculative decoding,
   context compression, long-context support).

### Acceptance Criteria
- `pleiades-re analyze <binary>` runs decompilation + LLM summary, outputs report.
- Box64 or QEMU user-mode installed and tested with a cross-arch binary in container.
- `pleiades-fuzz <target>` generates harness, runs AFL++/libFuzzer, reports crashes.
- A 4-bit quantized Mistral/Llama model is loadable via llama.cpp inside the container.

---

## Bundle 3 — Security Package Catalog Deployment

### Background
Verified conservative security package catalog across Ubuntu, Arch, Artix, Gentoo, and OpenWRT.
32 Gentoo atoms verified in ::gentoo overlay. Cross-distro equivalents mapped. Categories:
cryptography, forensics, network analysis, firewall, VPN, anonymity, intrusion detection,
offensive (hashcat, hydra, sqlmap, aircrack-ng), hardening (lynis, rkhunter, fail2ban).

### Goals
1. Deploy all 32 verified Gentoo security atoms into the container via `emerge --fetchonly`
   then staged install, controlled by the omnipkg plugin.
2. Generate distro-agnostic install scripts that omnipkg can dispatch to the right package
   manager depending on the active Bedrock stratum.
3. Wire all installed security tools into the Pleiades Team capability registry (pleiadesctl).
4. Create an offline mirror/bundle of the security packages for air-gapped deployment.

### Acceptance Criteria
- `pleiadesctl list-capabilities` shows all 32 security tools post-install.
- `omnipkg security-baseline install` installs the full catalog without manual intervention.
- Offline bundle at `/workspaces/gentoo/offline/security-pkgs/` contains all fetched packages.
- `pleiadesctl verify-tools` checks that each binary is present and executable.

---

## Bundle 4 — AI Converter / MCP Server Pipeline

### Background
Research covers the pipeline: Repo/Paper/API/docs → Gitingest/Repomix (context packer) →
Aider/OpenHands/DeepCode/Paper2Code (code agent) → FastMCP/mcpify/openapi-mcp-codegen (MCP
server generator) → usable MCP tool. Monster stack: DeepCode, Aider, OpenHands, Repomix,
Gitingest, FastMCP, fastapi_mcp, MCPForge, openapi-mcp-codegen, mcpify, Paper2Code.

### Goals
1. Implement a `repo2mcp` pipeline script: takes a GitHub URL, runs Gitingest/Repomix to
   pack context, feeds to Aider/OpenHands for code understanding, generates FastMCP server stub.
2. Implement a `paper2mcp` pipeline: fetches arXiv paper, runs Paper2Code to generate
   implementation, wraps generated code as an MCP tool/skill.
3. Implement `openapi2mcp`: takes an OpenAPI spec, generates an MCP server using
   openapi-mcp-codegen or fastapi_mcp.
4. Wire all three converters as Pleiades Team operator commands (`pleiadesctl convert repo2mcp`,
   `pleiadesctl convert paper2mcp`, `pleiadesctl convert openapi2mcp`).

### Acceptance Criteria
- `pleiadesctl convert repo2mcp https://github.com/example/repo` produces a working MCP server stub.
- `pleiadesctl convert paper2mcp https://arxiv.org/abs/2605.08419` produces skeleton implementation.
- `pleiadesctl convert openapi2mcp <spec.yaml>` generates a runnable FastMCP server.
- All three pipelines are tested end-to-end in the container.

---

## Cross-Bundle: Omnipkg & alien-bsd Extensions

### Goals
1. Extend omnipkg to support the compiler/toolchain ecosystem (stage 1: fetch Zig/Nim/V tarballs).
2. Extend alien-bsd to handle Nim `.nimble` packages and V's `vpkg` format.
3. Add a Wasmtime/jco WASM runtime stratum to the Asterope.sh BSD compatibility layer.
4. Test disaster recovery: rebuild the full Pleiades Team container from scratch using all new
   pipelines (this feeds into existing task #4).

### Acceptance Criteria
- `omnipkg install zig` and `omnipkg install nim` work end-to-end.
- `alien-bsd --from nimble <pkg.nimble>` produces a Gentoo ebuild skeleton.
- Asterope.sh can activate a WASM runtime stratum.
- Disaster recovery test completes successfully with security catalog + compiler toolchains.
