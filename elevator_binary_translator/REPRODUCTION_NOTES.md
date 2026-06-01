# Reproduction Notes — Elevator Binary Translator

**Paper:** Deterministic Fully-Static Whole-Binary Translation without Heuristics
**Authors:** Hongyu Chen, James McGowan, Michael Franz
**ArXiv:** 2605.08419
**Implementation mode:** minimal | Framework: Python (no ML framework)

---

## Critical caveat

**The paper PDF was unalcyoneilable at implementation time.** The arxiv HTML
fetcher retrieved only the abstract page. Every implementation decision that
goes beyond the abstract is [UNSPECIFIED] and flagged with that tag in code.

This implementation faithfully represents the *architecture* described in the
abstract. It cannot reproduce the *internals* without the full paper.

---

## What is SPECIFIED (from abstract)

| Item | Specification |
|------|--------------|
| Source ISA | x86-64 |
| Target ISA | AArch64 |
| Translation mode | Static (ahead-of-time), whole-binary |
| Byte roles | Data, opcode, opcode-argument (explicitly named) |
| Pruning criterion | Paths leading to abnormal termination |
| Translation mechanism | Code "tiles" derived from ISA description |
| Output | Self-contained binary, no runtime component |
| Performance target | "on par with or better than QEMU user-mode JIT" |
| Evaluation corpus | SPECint 2006, "diverse corpus of real-world binaries" |

---

## What is UNSPECIFIED (implementation choices made)

### 1. Tile grammar and derivation
**Paper says:** "tiles automatically derived from a high-level description of the source ISA"
**Unknown:** The ISA description language, the tile derivation algorithm, the tile grammar.
**Our choice:** Hand-written tiles for ~10 x86-64 instructions (demonstration only).
**Alternatives:** ISLE-like grammar (as in Cranelift), Burg-style tree patterns, machine-generated from x86 XML spec.

### 2. CFG representation
**Paper says:** "separate control flow paths for all interpretations"
**Unknown:** Whether CFG is byte-level, instruction-level, or basic-block-level; how overlapping instruction streams are represented.
**Our choice:** Instruction-level nodes; separate node per interpretation per address.
**Alternatives:** Supergraph with shared structural nodes, separate per-interpretation CFGs.

### 3. Pruning algorithm
**Paper says:** "pruning only those leading to abnormal termination"
**Unknown:** What counts as abnormal termination, the analysis algorithm (dataflow, symbolic execution, SAT), whether it's a single pass or fixpoint.
**Our choice:** Two passes: (1) prune capstone-invalid decodes, (2) prune dead code from entry.
**Alternatives:** Abstract interpretation, model checking, backward reachability from trap instructions.

### 4. Register allocation / mapping
**Paper says:** Nothing about register allocation.
**Unknown:** Whether Elevator uses a fixed register mapping, spills, or SSA-based allocation.
**Our choice:** Fixed mapping (rax→x0, rbx→x19, etc.) consistent with common x86-to-AArch64 conventions.
**Impact:** High — incorrect register mapping will produce wrong translations.

### 5. Stack ABI mismatch
**Paper says:** Nothing about stack layout.
**Unknown:** How Elevator reconciles x86-64 push (8-byte) with AArch64 SP alignment (must be 16-byte).
**Our choice:** Use 16-byte slots for push/pop, accepting wasted space.
**Alternatives:** Rewrite stack operations to use a separate shadow stack; adjust all frame offsets.

### 6. Indirect branch handling
**Paper says:** "whole-binary translation" (implies all branches must be resolved).
**Unknown:** How runtime-computed jump targets are handled in a static translation.
**Our choice:** Stub indirect branches with `brk` (breakpoint). Full Elevator likely pre-computes all reachable targets from the CFG.
**This is a fundamental gap:** Indirect branches are the hardest part of static binary translation and the paper's main contribution likely addresses them. Without the paper, we cannot implement this.

### 7. Overlapping interpretation merging
**Paper says:** "produces a separate translation for each feasible interpretation"
**Unknown:** How the separate translations are woven together in the output binary (trampolines? padding? selector code?).
**Our choice:** Emit separate labeled blocks; merging is a TODO.
**This is likely the paper's core novelty** — the output binary structure.

### 8. Entry point detection
**Paper says:** "without debug information, source code, or assumptions about code layout"
**Unknown:** How the entry point is identified without debug info.
**Our choice:** Parse ELF e_entry field (always present in ELF).
**Note:** The paper says "no assumptions about code layout," which may refer to data-vs-code layout, not the ELF entry point.

### 9. PLT/GOT and dynamic linking
**Paper says:** "entire x86-64 executables"
**Unknown:** How dynamically-linked binaries (with PLT stubs) are handled.
**Our choice:** Not implemented (fall through to untiled stub).

---

## Scope decisions

### Implemented
- Multi-interpretation byte analysis (`interpreter.py`) — core contribution
- Multi-interpretation CFG (`cfg.py`) — necessary for understanding translation
- Pruner skeleton (`pruner.py`) — core contribution (partially)
- Tile interface + small x86→AArch64 tile set (`tiles.py`, `x86_to_aarch64.py`) — core contribution (skeleton)
- Orchestrator (`translator.py`) — demonstrates full pipeline

### Intentionally excluded
- Full ELF binary emission — requires linker, out of scope
- SPECint 2006 evaluation — benchmark suite not publicly alcyoneilable
- QEMU comparison harness — out of scope (baseline, not contribution)
- ISA description compiler — paper's novelty, completely unspecified

### Would need for full reproduction
- Full paper PDF (§3 method, §4 tile grammar, §5 evaluation details)
- The ISA description file used by Elevator
- The tile generator (described as "automatically derived")
- The complete tile set for x86-64 (hundreds of instructions)
- The output binary linker/formatter

---

## How to get the full paper

```
# Try direct PDF download (may work after publication servers update)
curl -L https://arxiv.org/pdf/2605.08419.pdf -o elevator.pdf

# Or HTML version
curl -L https://ar5iv.labs.arxiv.org/html/2605.08419 -o elevator.html
```

Once you have the paper, the [UNSPECIFIED] items above can be resolved
by reading the method section (§3), tile grammar (§4), and appendices.

---

## Unresolved items requiring full paper

1. Overlapping interpretation merging in output binary
2. Indirect branch pre-computation algorithm
3. Tile grammar formal definition
4. Complete register allocation strategy
5. PLT/GOT/dynamic linking handling
6. Pruning algorithm (is it a fixpoint? backward analysis?)
7. Code size expansion formula
