# RePro — Reflective Paper-to-Code Reproduction

Implementation of **RePro** from:
> *RePro: Reflective Paper-to-Code Reproduction Enabled by Fine-Grained Verification* (2025)  
> Mingyang Zhou, Quanming Yao, Lun Du, Lanning Wei, Da Zheng  
> arXiv: 2508.16671

## Overview

RePro is a two-stage agentic pipeline for automatically reproducing research paper code:

1. **Supervisory Signal Design (§3.1)** — Extracts a paper "fingerprint": a set of atomic fact-scope criteria that the reproduced code must satisfy.
2. **Reflective Code Development (§3.2)** — Generates initial code, then iteratively verifies each criterion, plans targeted fixes, and refines the code. Up to 4 iterations; early-stops when all criteria pass.

## Install

```bash
pip install litellm sentence-transformers scikit-learn numpy
```

Set your LLM API keys:
```bash
export DEEPSEEK_API_KEY=...   # Deepseek-V3 (supervisory signal + verification)
export OPENAI_API_KEY=...     # o3-mini-high (implementation + planning + refinement)
```

## Quick Start

```python
from pathlib import Path
from repro import run_repro

result = run_repro(
    title="My Paper Title",
    intro_text="Abstract and introduction text...",
    experiment_text="Experiments section text...",
    paragraphs=["paragraph 1...", "paragraph 2...", ...],
    output_dir=Path("output/my_paper"),
)
print(result.summary())
```

## File Structure

```
repro/
  repro/
    prompts.py            # verbatim LLM prompts (Appendix Figs 6-16)
    embeddings.py         # all-MiniLM-L6-v2 wrapper
    supervisory_signal.py # §3.1 fingerprint extraction pipeline
    code_development.py   # §3.2 verify/plan/refine loop
    pipeline.py           # end-to-end runner
  configs/
    base.yaml             # all §-cited parameters
  notebooks/
    walkthrough.ipynb     # paper § ↔ code walkthrough
  REPRODUCTION_NOTES.md   # unspecified choices + scope
```

## LLM Assignments (§4.1)

| Stage | Model |
|-------|-------|
| Guide extraction (all levels) | Deepseek-V3 |
| Verification | Deepseek-V3 |
| Initial implementation | o3-mini-high |
| Revision planning | o3-mini-high |
| Refinement | o3-mini-high |
| Embeddings | all-MiniLM-L6-v2 |
