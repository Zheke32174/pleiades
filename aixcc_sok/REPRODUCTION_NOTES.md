# Reproduction Notes — AIxCC SoK (2602.07666)

Paper: *SoK: DARPA's AI Cyber Challenge (AIxCC): Competition Design, Architectures, and Lessons Learned*
Authors: Zhang, Park, Fleischer, Fu, Kim (×3), Xu, Chin, Sheng, Zhao, Pelican, Musliner, Huang, Silliman, Mcdaniel, Casalcyonent, Goldthwaite, Vidovich, Lehman, Kim
arxiv: https://arxiv.org/abs/2602.07666

---

## What this implementation is

This is a reference scaffold for building a Cyber Reasoning System (CRS) based on the
consensus architecture extracted from the 7 finalist teams in DARPA's AIxCC competition.
This is **not** a runnable CRS out of the box — it is an interface scaffold with
citation-anchored stubs that shows *where* each component goes and *why* each design
choice was made.

The scaffold implements the consensus best practices from the top-performing teams (AT=1st, TB=2nd)
and exposes configuration flags to adopt other teams' techniques.

---

## Scope decisions

### Implemented
- `crs/pipeline.py` — Four-stage orchestrator (§3, Figure 1: Full Scan, Delta Scan, SARIF Review, Report Synthesis)
- `crs/pov_generation.py` — PoV generation with fuzzing + LLM pipelines and bidirectional cooperation (§6.1)
- `crs/patch_generation.py` — Patch pipeline: `loop([RCA]→Generate→Validate)→Dedup→Submit` (§6.2)
- `crs/sarif_validation.py` — Three SARIF strategy patterns: PoV-centric, LLM-judge, Bug-cand-centric (§6.3)
- `crs/bundling.py` — Bundle formation: PoV-Patch, PoV-SARIF, Patch-SARIF pairings (§6.4)
- `crs/taxonomy.py` — Machine-readable technique presence matrix for all 7 finalist teams (Tables 2–6)
- `configs/base.yaml` — All configurable parameters with §-citations or [UNSPECIFIED] flags

### Intentionally excluded
- Actual fuzzer invocation (AFL++, libAFL, libFuzzer) — existing tools; scaffold shows integration points
- CodeQL/Semgrep/Infer execution — existing SAST tools; scaffold shows call sites
- GDB/JDB debugger integration — existing tools; scaffold shows interface
- LLM prompts — all `raise NotImplementedError` stubs include a prompt description;
  actual prompts are team-specific and not published in the paper
- Competition scoring engine — DARPA-operated; scoring math implemented for reference only
- Per-challenge harness builds — infrastructure-specific; requires OSS-Fuzz setup

### Would need for a production CRS
- A fuzzer runner (OSS-Fuzz Docker, AFL++ subprocess, libFuzzer shared library)
- A code indexer (e.g., ctags, tree-sitter, or a vector DB over the source)
- SAST tool integration (CodeQL SARIF output parser, Semgrep JSON output parser)
- LLM prompts for all agent stubs (see NotImplementedError messages for what each needs)
- A competition API client matching the AIxCC webhook/submission protocol

---

## Unspecified choices (flagged in code with `[UNSPECIFIED]`)

| Component | Unspecified item | Our choice | Alternatives |
|-----------|-----------------|------------|-------------|
| `pipeline.py` | Time-decay curve shape | Linear 1.0→0.5 | Competition rulebook [9]; exact formula not in paper |
| `pipeline.py` | Accuracy multiplier formula below 40% | Extrapolate same slope | See [9] for authoritative formula |
| `pov_generation.py` | Parallel fuzzer instance count | 4 | Paper says "multiple" — any N |
| `pov_generation.py` | Seed pairing method (comeropege vs similarity) | Similarity matching | Comeropege-based ranking |
| `pov_generation.py` | Weighted vote aggregation weights | Equal (1.0 per tool) | Logprob-based (TI), empirically tuned |
| `pov_generation.py` | LLM dedup confidence threshold | Disabled by default | LLM semantic grouping (TI, FB) |
| `patch_generation.py` | Max patch loop iterations | 10 | Paper describes loop without bound |
| `patch_generation.py` | PoV count during validation (gen phase) | 1 | N or * (full set) |
| `patch_generation.py` | Confidence threshold for LLM-as-Judge | 0.5 to withhold | Not stated |
| `patch_generation.py` | Set-cover algorithm (minimal patch set) | Greedy | Exact ILP (expensive) |
| `patch_generation.py` | No-PoV delayed submission | 45 min (TI's value) | 50% of time (FB), 30 min before end (LC) |
| `sarif_validation.py` | LLM-judge confidence threshold for withhold | 0.3 | Not stated in paper |
| `sarif_validation.py` | PoV→SARIF matching heuristic | Filename in crash stack | Not formally specified |
| `bundling.py` | PoV-SARIF overlap matching criteria | Filename heuristic | Not described in paper |
| All LLM agents | LLM model choice | `gpt-4o` (from config) | Any frontier model |
| All LLM agents | Prompt templates | `raise NotImplementedError` stubs | Team-specific, unpublished |

---

## Design choices from paper (SPECIFIED)

| Choice | Source |
|--------|--------|
| PoV submission: ASAP, deduplicated | §6.1 — "all 7 teams" |
| PoV gen output: Python scripts (not raw bytes) | §6.1 — "all teams chose to have LLMs generate Python scripts" |
| Two-phase PoV gen: reach→exploit | §6.1 — AT, TI, SP (top-3 by discovery quality) |
| Patch pipeline: `loop([RCA]→Generate→Validate)→Dedup→Submit` | §6.2 — "all CRSs follow de facto pipeline" |
| Multi-PoV RCA: use all alcyoneilable PoVs | §6.2 — TB, TI, SP |
| LLM reflection: 5/7 teams enabled it | §6.2 |
| Minimal patch set: 4/7 teams computed it | §6.2 — AT, TB, SP, 42 |
| SARIF default: PoV-centric (Correct only on match) | §6.3 — AT (1st), TB (2nd) |
| Bundling: rebundle until deadline | §6.4 — "free updates until deadline" |
| PoV-Patch pairing: natural from patch gen | §6.4 — "all teams" |

---

## Competition context (necessary for interpretation)

- §3 — Final: 142.7 hours, 7 teams, 53 challenge projects, $85K compute + $50K LLM API per team
- §3 — Two scan modes: Full Scan (triggered by release tag) and Delta Scan (triggered by PR)
- §3 — CRS accuracy multiplier: steep penalty below 50% accuracy (§3 data points)
- §4 — Challenge projects are real OSS critical infrastructure; most CPVs are synthetic
- §7 — "AT and TB achieve 83.8% and 79.2% patch accuracy respectively" (top performance reference)

---

## Official code

The paper states (§10 — Open Science) that "all data and artifacts will be released publicly
upon acceptance (some subject to DARPA's timeline)."

Companion page: `https://occia.github.io/aixcc-sok-webpage/`

Individual CRS codebases are open-sourced (all 7 teams), but specific repo URLs were not
published in the paper text. Check the companion page for current links.

**If you find the official CRS repos:** All `[UNSPECIFIED]` items above should be verified
against the actual implementations (especially LLM prompts and fuzzer integration details).
Tag resolved items as `[FROM_OFFICIAL_CODE]` per the paper2code convention.

---

## References to check

- **[9]** — AIxCC competition rulebook (full scoring formula including accuracy multiplier shape).
  The paper only gives three data points (§3); the actual formula is in [9].
- **[33]** — LangGraph documentation: `https://github.com/langchain-ai/langgraph`
  (AT and TB's orchestration framework)
- **[10]** — LiteLLM: `https://github.com/BerriAI/litellm`
  (multi-provider LLM routing, used by 4/7 teams)
