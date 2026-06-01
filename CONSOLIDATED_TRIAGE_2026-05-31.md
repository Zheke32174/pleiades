# Cross-Bundle Triage & Integration Plan

Generated: 2026-05-31 — consolidating four research bundles against the live pleiades-team / factory stack.

## What the bundles actually are

These are **research bibliographies + GitHub catalogs + package lists**, not papers or repos themselves. Total surface:

| Bundle | Papers | Repos | Other | Theme |
|---|---:|---:|---|---|
| ai_re_cyber_research_bundle | 86 | 30 | 11 MS docs, 25 USENIX PDFs, 5 DARPA, 13 misc | AI for reverse engineering, decompilation, cross-ISA bridging, vuln discovery, harnessing |
| security_pkg_catalog_parsed | 0 | 0 | 35 verified packages × 5 distros, fetch scripts | Operational security tooling layer |
| github_replacer_research_bundle | 0 | 45 | — | Compiler/toolchain/AI replacers for Zig/Zen-C surface |
| ai_converter_research_bundle | 29 | 92 | 8 indexes, 168 deduped URLs | Anything→code/skill/MCP conversion pipelines |
| **Total unique** | ~115 | ~165 | — | — |

## Already cloned under `/workspaces/gentoo/tools/` — do not re-pull

These are the bundle entries that overlap with your existing tree (verified against `tools/` listing):

| Bundle entry | Local clone | Notes |
|---|---|---|
| `going-doer/Paper2Code` | `tools/paper2code` | Wired into factory toolchain.json |
| `continual-harness` (paper 2605.09998) | `tools/continual-harness` + `/workspaces/gentoo/continual_harness/` | Implementation already generated |
| `hermes-agent-self-evolution` | `tools/hermes-agent-self-evolution` | Editable install done |
| `MemOS` (paper 2507.03724) | `tools/MemOS` | Cloned; not yet wired |
| `chorus` (human-in-the-loop) | `tools/chorus` | AIOS adapter exists |
| `codegraph` / `codeindex` | `tools/codegraph`, `tools/codeindex` | Repo-graph navigation |
| `agent-rules-books` | `tools/agent-rules-books` | Skill source |
| `Elevator` static binary translator (paper 2605.08419) | `/workspaces/gentoo/elevator_binary_translator` | Highest-priority RE pipeline anchor |

**Implication:** the integration work is wiring, not cloning, for the items above.

---

## TIER 1 — Highest priority new pulls

Order matches likely user goals: extend factory toolchain → RE pipeline → security validators → cross-arch lanes.

### 1A. paper2code targets that should run next (papers)

Picked from `ai_converter` bundle's "skill / paper-to-code" cluster — these directly upgrade your existing paper2code → Hermes → continual-harness chain.

| arxiv | Title | Why it matters here |
|---|---|---|
| 2504.17192 | **Paper2Code: Automating Code Generation from Scientific Papers** | The named system your skill is descended from — read for missing stages |
| 2508.16671 | **RePro: Reflective Paper-to-Code Reproduction with Fine-Grained Verification** | Add a verification pass after Stage 4 |
| 2504.01848 | **PaperBench: Evaluating AI's Ability to Replicate AI Research** | Use as your own eval set; ties into pleiades-team factory's NQS scoring |
| 2604.01687 | **CoEvoSkills: Self-Evolving Agent Skills via Co-Evolutionary Verification** | Multi-file skill packages + co-evolutionary verification — pairs with Hermes/GEPA |
| 2604.04804 | **SkillX: Skill Knowledge Bases for Agents** | Persistent reusable skill KB |
| 2605.10999 | **SkillGen: Verified Inference-Time Agent Skill Synthesis** | Skills from successful + failed trajectories — exactly your continual-harness signature |
| 2605.18693 | **SkillGenBench** | Benchmark to drop into pleiades-team evaluation |
| 2605.27366 | **MUSE-Autoskill** (already partially fetched per S91/S92) | Finish Stage 4 codegen |
| 2503.07358 | **RepoST: Repo-Level Coding Environment with Sandbox Testing** | Sandbox testing layer for paper2code outputs |
| 2507.16044 | **From REST to MCP: Empirical Study of API Wrapping** | Most direct REST/OpenAPI → MCP server reference |
| 2506.19998 | **Doc2Agent** | API docs → executable Python tools |

### 1B. paper2code targets for the RE / cyber pipeline

From `ai_re_cyber` — these are the "prioritized our-stack" items the bundle itself flags as core.

| arxiv | Title | Pipeline lane |
|---|---|---|
| 2605.08419 | **Elevator: Deterministic Fully-Static Whole-Binary Translation** | Static x86→AArch64 lane (binary already cloned, paper not yet implemented) |
| 2405.09132 | **EFACT: External Function Auto-Completion for Static Lifting** | Pairs with Elevator |
| 2404.16041 | **Forklift: Extensible Neural Lifter** | Neural lifting lane |
| 2403.05286 | **LLM4Decompile** | Core decompilation lane |
| 2605.11501 | **Decaf: Improved Neural Decompilation with Automatic Reranking** | Reranker/refiner stage |
| 2605.02121 | **SCRIBE: Binary-Aware Recompilation Patching** | Validator stage |
| 2603.08225 | **Practical Type Inference** | Type recovery stage |
| 2405.17238 | **IRIS: LLM-Assisted Static Analysis for Vuln Detection** | Cyber loop |
| 2506.23644 | **QLPro: Automated Vuln Discovery via LLM + CodeQL** | Cyber loop |
| 2602.18689 | **Stitch: Automatic, Expressive Fuzzing** | Harness loop |
| 2512.03420 | **HarnessAgent: Tool-Augmented LLM Pipelines for Fuzz Harnesses** | Harness loop |
| 2601.17471 | **PatchIsland: LLM Orchestration for Continuous Vuln Repair** | Repair loop |
| 2603.08566 | **OSS-CRS: Liberating AIxCC Cyber Reasoning Systems** | Full AIxCC loop reference |
| 2602.07666 | **SoK: DARPA AIxCC Competition Lessons** | Architecture survey to read before any of the above |

### 1C. Repos to clone (Tier 1)

From `ai_converter` "monster stack" + `ai_re_cyber` GitHub list, minus already-cloned:

```bash
# AI converter / skill stack
git clone https://github.com/HKUDS/DeepCode               # paper-to-code multi-agent
git clone https://github.com/OpenHands/OpenHands          # repo-to-code agent (was OpenDevin)
git clone https://github.com/yamadashy/repomix            # repo context packer
git clone https://github.com/coderamp-labs/gitingest      # alt context packer
git clone https://github.com/PrefectHQ/fastmcp            # canonical MCP server framework
git clone https://github.com/tadata-org/fastapi_mcp      # FastAPI → MCP
git clone https://github.com/cnoe-io/openapi-mcp-codegen # OpenAPI → MCP
git clone https://github.com/Zhang-Henry/CoEvoSkills      # skill self-evolution (pairs with paper 2604.01687)
git clone https://github.com/zjunlp/SkillX                # skill KB (pairs with 2604.04804)
git clone https://github.com/yccm/SkillGen                # inference-time skill synth (pairs with 2605.10999)

# RE / cyber tooling
git clone https://github.com/nationalsecurityagency/ghidra # decompilation backbone
git clone https://github.com/angr/angr                     # symbolic execution
git clone https://github.com/GrammaTech/ddisasm            # datalog disassembly
git clone https://github.com/lifting-bits/remill           # lifter
git clone https://github.com/lifting-bits/mcsema           # binary→LLVM IR
git clone https://github.com/lt-asset/resym                # ReSym type recovery
git clone https://github.com/hexhive/retrowrite            # static rewriting
git clone https://github.com/FEX-Emu/FEX                   # x86→ARM dynamic translation
git clone https://github.com/ptitSeb/box64                 # x86_64→ARM dynamic translation
git clone https://github.com/revng/revng                   # lifter/decompiler pipeline
git clone https://github.com/microsoft/WSL                 # WSL open-source (toolchain plane)
```

---

## TIER 2 — Useful but defer until Tier 1 settles

### 2A. Compiler / toolchain replacers (`github_replacer` bundle)

The bundle's premise — "replacements for Zen-C and Zig" — is broader than the user's current focus. The truly useful slice for the current factory stack:

| Repo | Why keep on radar |
|---|---|
| `ziglang/zig` | Cross-compile toolchain — relevant to ARM bridging |
| `bytecodealliance/wasmtime` | WASM runtime for sandboxed tool execution |
| `bytecodealliance/jco` | JS→WASM components |
| `astral-sh/ruff` + `biomejs/biome` + `oxc-project/oxc` | Fast linters; useful as paper2code output validators |
| `swc-project/swc` | TS/JS transpilation if any agent UI is built |
| `Aider-AI/aider` + `openai/codex` | Already in your factory model dispatch; just bookmark |
| `Zheke32174/{alien,scandroid,Tracendroid,underlode}` | **Your own repos** — not external; verify these are still the intended public set |

**Skip from this bundle:** `Ace17/toolchains`, `CE-Programming/toolchain`, `joshbirk/zen-compiler`, `gittup/tup`, `build2/build2`, `michaelforney/cproc`, `9cc`, `chibicc`, `mrustc`, `TinyCC`, `TypeScriptToLua`, `conan-io/conan`, `hermetic_cc_toolchain`, `openhwgroup/programs`, `z-libs/Zen-C`, `z-libs/zenc-vscode`, `zenlang-rs/compiler` — niche/legacy or duplicate categories already covered by Zig/Wasmtime/Ruff/Oxc.

### 2B. Security packages (`security_pkg_catalog_parsed`)

The catalog is small and operational. Recommended action: **install only on the pleiades-team Gentoo container, not in WSL host or codespace.**

High-value subset for the pleiades-team factory:
```
yara, yara-x, suricata, fail2ban, nmap, wireshark, tcpdump, hashcat, john,
hydra, sqlmap, lynis, rkhunter, chkrootkit, binwalk, sleuthkit, volatility3,
aircrack-ng, openvpn, wireguard-tools, strongswan, tor, torsocks, nftables,
iptables, openssh, cryptsetup, tpm2-tools, efitools, sbsigntools, certbot,
easy-rsa, gnupg, age, linux-hardened
```

The Gentoo emerge fetch list in `gentoo_fetch_sources.sh` is the most complete and matches your stage3 setup.

### 2C. Secondary RE / cyber papers

| arxiv | Title | Use case |
|---|---|---|
| 2505.12668 | Decompile-Bench (1M binary-source pairs) | Benchmark dataset |
| 2402.16928 | CLAP: Binary code repr w/ NL supervision | Embedding for retrieval |
| 2405.19581 | Source Code Foundation Models as Binary KBs | Symbol recovery |
| 2403.18403 | FoC: Crypto function ID in stripped binaries | Specialized RE |
| 2604.15136 | Feedback-Driven Execution for LLM Binary Analysis | Execution-grounded loop |
| 2605.10597 | CrackMeBench: Binary RE for Agents | Eval set |
| 2604.08083 | Can LLMs Deobfuscate Binary Code? | Capability ceiling check |
| 2406.11346 | WaDec: WebAssembly Decompilation | WASM-specific lane |
| 2506.19624 | Smart contract decompilation w/ LLM | Domain extension |
| 2202.01142 | Pop Quiz: LLM RE? | Historical baseline |

### 2D. AI optimization / harness papers

| arxiv | Title | Already-relevant to your stack |
|---|---|---|
| 2605.18747 | **Toward Executable, Verifiable, Stateful Agent Systems** | Canonical reference for your factory design |
| 2603.07427 | Synthesizing Executable Test Environments for Frontier AI Safety | Eval harness construction |
| 2604.17056 | RLM-on-KG | Determinism-first retrieval pattern |
| 2401.10774 | Medusa: Multi-head speculative decoding | Local inference speedup |
| 2406.16858 | EAGLE-2 | Same family — pick one |
| 2309.17453 | StreamingLLM | Long-context |
| 2505.18092 | QwenLong-CPRS | Context compression |
| 2502.13189 | MoBA: Mixture of Block Attention | Long-context |
| 2211.10435 | PAL: Program-Aided LMs | Foundational |
| 2409.16694 | Low-bit LLM survey | Quantization reference |
| 2410.19878 | PEFT survey | Adapter reference |

---

## TIER 3 — Skip or low priority

- **`combined_parsed_urls.md` arxiv tail** (everything in `ai_re_cyber/combined_parsed_urls.md` that is NOT in `categorized_bibliography.md`) — uncategorized residue from URL scraping; many are tangential or duplicates of v1/v2/v3 of the same paper.
- **`ai_converter` "Discussions / Issues / Docs"** category — GitHub discussion threads, not actionable code.
- **`ai_converter` "Awesome lists"** — useful for discovery, but bookmark rather than clone; one curated list is enough (recommend `kyrolabs/awesome-agents` or `FoundationAgents/awesome-foundation-agents`).
- **Duplicate paper IDs across bundles** — e.g. paper2code (2504.17192) appears in both `ai_converter` and implicitly in `ai_re_cyber` via the skill itself.
- **Zheke32174 entries in `github_replacer`** — these are your own repos, not external candidates; remove from the "replacer" framing.

---

## Cross-bundle integration map

The four bundles are not independent — they layer:

```
   ai_converter_research_bundle
   (Paper→Code, Repo→Code, Anything→Skill, API→MCP)
                 |  feeds
                 v
   ai_re_cyber_research_bundle
   (RE pipelines, decompilation, vuln, cross-ISA, harness)
                 |  wires into
                 v
   Existing factory:
   paper2code -> Hermes -> continual-harness -> pleiades-team
   + AIOS kernel + MemOS storage + Chorus approval
                 |  uses
                 v
   github_replacer_research_bundle   <-- compiler/toolchain lane
   security_pkg_catalog_parsed       <-- validator/sandbox lane
```

### Concrete overlaps worth noting

1. **`going-doer/Paper2Code` repo** appears in `ai_converter` AND is already cloned. The paper (arxiv 2504.17192) appears in `ai_converter` paper list. → Read the paper to upgrade your skill's stages.
2. **AIxCC papers cluster** (2603.08566, 2602.07666, 2601.17471, 2603.10072, 2605.04251) all describe interlocking pieces of a cyber reasoning system. Implement as a single multi-paper batch in paper2code rather than one-at-a-time — they share architecture.
3. **`paper2code` MCP path is missing.** Bundle 4 has heavy MCP comeropege (fastmcp, fastapi_mcp, openapi-mcp-codegen, ToolFactory, Doc2Agent, OASBuilder), but your factory does not yet expose paper2code outputs as MCP tools. This is the highest-lemeropege gap.
4. **Elevator paper already has a binary** at `/workspaces/gentoo/elevator_binary_translator/` but the paper2code run hasn't happened. Combine with EFACT (2405.09132) — Elevator + EFACT is a two-paper unit per the literature.
5. **Skill-generation cluster** (CoEvoSkills + SkillX + SkillGen + MUSE-Autoskill + MIND-Skill) directly competes with your existing Hermes/GEPA approach. Implement *one* of these first as a comparison rather than implementing all five.

---

## Recommended next 5 actions

1. **Run paper2code on the AIxCC SoK** (2602.07666) first — it's the architecture survey that explains how all the other RE/cyber papers fit. Cheaper than implementing them blind.
2. **Run paper2code on RePro** (2508.16671) and graft its verification pass into your own paper2code Stage 5. Self-improving the skill is highest lemeropege.
3. **Run paper2code on Elevator** (2605.08419) + **EFACT** (2405.09132) as a unit — Elevator binary is already on disk, so you can validate against the reference implementation.
4. **Clone the 10 Tier 1 repos** from `ai_converter` (DeepCode, OpenHands, repomix, gitingest, fastmcp, fastapi_mcp, openapi-mcp-codegen, CoEvoSkills, SkillX, SkillGen) into `tools/`, then add them to `.octo/factory/toolchain.json`.
5. **Decide one skill-gen system** (CoEvoSkills vs SkillX vs SkillGen vs MUSE-Autoskill) and implement that one fully before touching the others, so you can benchmark against Hermes.

---

## What is NOT useful and why

| Item | Why skip |
|---|---|
| `github_replacer` Zen-C / Zen-compiler entries | Niche compiler experiments; you already have Zig + Wasmtime |
| Round-1-only "unclassified parsed candidate" repos in `github_replacer` | Most are decade-old toy compilers (9cc, chibicc, tinycc) |
| Discussion-thread URLs in `ai_converter` | Not code; informational only |
| Duplicate v1/v2/v3 arxiv HTML URLs in `ai_re_cyber/combined_parsed_urls.md` | Already covered by the categorized bibliography |
| USENIX PDF URLs without a paper match | Useful for one-off reads, not for paper2code (which needs arxiv IDs) |
| Microsoft Learn docs | Reference material; bookmark, don't ingest |
| AIxCC competition pages | Marketing/news; the SoK paper (2602.07666) is the substantive version |
| Zheke32174 repos under "replacer" framing | Your own repos — they belong in your project list, not a replacer triage |

---

## Quick stats

- **Total unique papers across bundles:** ~115 arxiv IDs
- **Already actionable (Tier 1A + 1B):** 25 papers
- **Already cloned repos:** 8 of the 165 mentioned
- **Tier 1 repos to clone next:** 20
- **Operational packages to install on Gentoo container:** 35
- **Items recommended to skip:** ~50% of `github_replacer` round 1, all discussion URLs, all duplicate HTML mirrors

---

## Files produced

- `CONSOLIDATED_TRIAGE_2026-05-31.md` (this file) at `/workspaces/gentoo/`

## Files NOT produced (intentionally)

- No code generated — bundles are catalogs, not implementations.
- No clones executed — Tier 1 repo list is a recipe, not a script run.
- No paper2code invocations — Tier 1A/1B paper IDs are queued, not executed. Each is a separate `/paper2code-skill <id>` run.
