# Reproduction Notes — RePro (arXiv 2508.16671)

## Unspecified Implementation Choices

| ID | Location | Paper text | Choice made | Rationale |
|----|----------|------------|-------------|-----------|
| UNSPECIFIED-1 | `CriteriaFilter._cluster_dedup` | "cluster-based dedup" | `AgglomerativeClustering`, cosine distance threshold 0.15 | No algorithm named; agglomerative with precomputed cosine distance is natural for sentence vectors |
| UNSPECIFIED-2 | `SourceGrounder.ground` | "top-3 paragraphs" | No similarity floor; always return top-3 | Paper does not mention a minimum threshold |
| UNSPECIFIED-3 | `embeddings.embed` | "all-MiniLM-L6-v2" | sentence-transformers default tokenisation | Not specified |
| UNSPECIFIED-4 | `GuideExtractor.extract_paragraph_sentences` | Level-3 extraction | One paragraph per LLM call | Paper does not state batching |
| UNSPECIFIED-5 | `SupervisorySignalPipeline.run` | No cap mentioned | No hard cap on criteria count | Paper does not set a maximum |
| UNSPECIFIED-6 | `Refiner.refine` | "targeted minimal edits" | Whole-file replacement per modified file | Sub-file patch format not specified |
| UNSPECIFIED-7 | `Verifier.verify_one` | Described as pass/fail + feedback | `{"status": "PASS"|"FAIL", "feedback": "..."}` JSON | Schema inferred from Figure 14 description |

## Scope Decisions

### Implemented
- Full §3.1 supervisory signal pipeline (3-level extraction → grounding → standardize → filter)
- Full §3.2 reflective code development (skeleton → fill → verify → plan → refine, ≤4 iterations)
- Verbatim prompts from Appendix Figures 6-16 in `repro/prompts.py`
- LiteLLM routing with §4.1-specified model assignments

### Not implemented (out of scope)
- PaperBench evaluation harness — the paper's *evaluation environment*, not its contribution
- Full end-to-end run on 20 ICML 2024 papers — requires paid LLM API access + compute
- Baselines (PaperCoder, AutoReproduce) — not this paper's contribution

## Key Results (for reference, §4.2 Table 1)
- RePro PRroot: **62.6%** (vs best baseline 49.6%)
- RePro PRleaf: **61.0%**
- Ablation w/o iterative refinement: PRroot 51.9% (-10.7 pp)
- Ablation w/o supervisory signal: PRroot 44.9% (-17.7 pp)
