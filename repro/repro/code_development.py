"""
Reflective Code Development (§3.2).

Initial implementation (skeleton → fill) → iterative verify/plan/refine loop.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from repro import prompts
from repro.supervisory_signal import Criterion, PaperGuide


# ── LLM caller (LiteLLM) ──────────────────────────────────────────────────────

def _call_llm(model: str, system: str, user: str) -> str:
    from litellm import completion
    resp = completion(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content.strip()


# ── §4.1 model assignments ────────────────────────────────────────────────────

IMPL_MODEL   = "o3-mini-high"   # initial implementation + refinement
PLAN_MODEL   = "o3-mini-high"   # revision planning
VERIFY_MODEL = "deepseek/deepseek-chat"  # verification


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class VerificationResult:
    criterion: Criterion
    status: str   # "PASS" | "FAIL"
    feedback: str

    @property
    def passed(self) -> bool:
        return self.status == "PASS"


@dataclass
class RevisionPlan:
    config_plan: str
    code_plan: str
    raw: str

    def __str__(self) -> str:
        return self.raw


@dataclass
class IterationRecord:
    iteration: int
    results: List[VerificationResult]
    plan: Optional[RevisionPlan]

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def n_pass(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def n_fail(self) -> int:
        return len(self.results) - self.n_pass


# ── Initial Implementer ────────────────────────────────────────────────────────

class InitialImplementer:
    """
    Two-phase initial implementation (§3.2):
    Phase 1 — skeleton using guide levels 1-2 (framework + configuration).
    Phase 2 — fill using guide level 3 (paragraph-level sentences).
    """

    def generate_skeleton(self, guide: PaperGuide) -> Dict[str, str]:
        """Phase 1: skeleton from framework + configuration guide."""
        raw = _call_llm(
            IMPL_MODEL,
            prompts.SKELETON_SYSTEM,
            prompts.SKELETON_USER_TEMPLATE.format(
                framework_guide=guide.framework,
                configuration_guide=guide.configuration,
            ),
        )
        return _parse_code_blocks(raw)

    def fill_skeleton(
        self, skeleton: Dict[str, str], guide: PaperGuide
    ) -> Dict[str, str]:
        """Phase 2: fill stubs using paragraph-level guidance."""
        skeleton_text = _format_file_blocks(skeleton)
        para_guide = "\n".join(f"- {s}" for s in guide.paragraphs)
        raw = _call_llm(
            IMPL_MODEL,
            prompts.FILL_SYSTEM,
            prompts.FILL_USER_TEMPLATE.format(
                skeleton_files=skeleton_text,
                paragraph_guide=para_guide,
            ),
        )
        updated = _parse_code_blocks(raw)
        # merge: keep skeleton files not touched by the fill pass
        result = dict(skeleton)
        result.update(updated)
        return result

    def implement(self, guide: PaperGuide) -> Dict[str, str]:
        skeleton = self.generate_skeleton(guide)
        return self.fill_skeleton(skeleton, guide)


# ── Verifier ──────────────────────────────────────────────────────────────────

class Verifier:
    """Per-criterion pass/fail verification (§3.2 + Figure 14)."""

    def verify_one(
        self,
        criterion: Criterion,
        code_files: Dict[str, str],
    ) -> VerificationResult:
        import json as _json

        code_text = _format_file_blocks(code_files)
        source = "\n".join(f"- {s}" for s in criterion.source_sentences)
        raw = _call_llm(
            VERIFY_MODEL,
            prompts.VERIFICATION_SYSTEM,
            prompts.VERIFICATION_USER_TEMPLATE.format(
                fact=criterion.fact,
                scope=criterion.scope,
                source_sentences=source or "(none)",
                code_files=code_text,
            ),
        )
        try:
            obj = _json.loads(raw)
            status = obj.get("status", "FAIL").upper()
            feedback = obj.get("feedback", raw)
        except (_json.JSONDecodeError, AttributeError):
            # fall back: look for PASS/FAIL keyword
            status = "PASS" if "PASS" in raw.upper() else "FAIL"
            feedback = raw

        return VerificationResult(
            criterion=criterion,
            status=status,
            feedback=feedback,
        )

    def verify_all(
        self,
        criteria: List[Criterion],
        code_files: Dict[str, str],
    ) -> List[VerificationResult]:
        return [self.verify_one(c, code_files) for c in criteria]


# ── Revision Planner ──────────────────────────────────────────────────────────

class RevisionPlanner:
    """Produce CONFIG PLAN + CODE PLAN over all failed criteria (§3.2 + Figs 15-16)."""

    def plan(
        self,
        failed: List[VerificationResult],
        code_files: Dict[str, str],
    ) -> RevisionPlan:
        failed_text = "\n\n".join(
            f"Criterion: {r.criterion}\nFeedback: {r.feedback}"
            for r in failed
        )
        code_summary = _summarize_code(code_files)
        raw = _call_llm(
            PLAN_MODEL,
            prompts.REVISION_PLANNING_SYSTEM,
            prompts.REVISION_PLANNING_USER_TEMPLATE.format(
                failed_criteria=failed_text,
                code_summary=code_summary,
            ),
        )
        config_plan, code_plan = _parse_revision_plan(raw)
        return RevisionPlan(config_plan=config_plan, code_plan=code_plan, raw=raw)


# ── Refiner ───────────────────────────────────────────────────────────────────

class Refiner:
    """Apply targeted minimal edits per the revision plan (§3.2)."""

    def refine(
        self,
        plan: RevisionPlan,
        code_files: Dict[str, str],
    ) -> Dict[str, str]:
        file_text = _format_file_blocks(code_files)
        raw = _call_llm(
            IMPL_MODEL,
            prompts.REFINEMENT_SYSTEM,
            prompts.REFINEMENT_USER_TEMPLATE.format(
                revision_plan=str(plan),
                file_contents=file_text,
            ),
        )
        updated = _parse_code_blocks(raw)
        result = dict(code_files)
        result.update(updated)
        return result


# ── RePro Pipeline Orchestrator ───────────────────────────────────────────────

class ReProPipeline:
    """
    Orchestrator: initial implementation → verify/plan/refine loop (§3.2).

    Max iterations: 4 (§4.1 SPECIFIED).
    Early stop: all criteria pass (§4.1 SPECIFIED).
    """

    MAX_ITERATIONS = 4  # §4.1

    def __init__(self):
        self.implementer = InitialImplementer()
        self.verifier = Verifier()
        self.planner = RevisionPlanner()
        self.refiner = Refiner()

    def run(
        self,
        guide: PaperGuide,
        fingerprint: List[Criterion],
        output_dir: Optional[Path] = None,
    ) -> Tuple[Dict[str, str], List[IterationRecord]]:
        """
        Returns (final_code_files, iteration_records).
        """
        code = self.implementer.implement(guide)
        records: List[IterationRecord] = []

        for iteration in range(1, self.MAX_ITERATIONS + 1):
            results = self.verifier.verify_all(fingerprint, code)
            failed = [r for r in results if not r.passed]

            plan: Optional[RevisionPlan] = None
            if failed:
                plan = self.planner.plan(failed, code)

            record = IterationRecord(
                iteration=iteration,
                results=results,
                plan=plan,
            )
            records.append(record)

            # persist iteration snapshot
            if output_dir is not None:
                _save_iteration(output_dir, iteration, code, record)

            # early stop if all criteria pass (§4.1)
            if record.all_passed:
                break

            if plan is not None:
                code = self.refiner.refine(plan, code)

        # write final files
        if output_dir is not None:
            _write_code_files(output_dir, code)

        return code, records


# ── I/O helpers ───────────────────────────────────────────────────────────────

def _parse_code_blocks(text: str) -> Dict[str, str]:
    """Extract ```python:path/to/file.py ... ``` blocks."""
    pattern = re.compile(
        r"```(?:python:)?([\w/.\-]+\.py)\n(.*?)```",
        re.DOTALL,
    )
    result: Dict[str, str] = {}
    for m in pattern.finditer(text):
        result[m.group(1)] = m.group(2)
    return result


def _format_file_blocks(files: Dict[str, str]) -> str:
    parts = []
    for path, content in files.items():
        parts.append(f"```python:{path}\n{content}\n```")
    return "\n\n".join(parts)


def _summarize_code(files: Dict[str, str]) -> str:
    lines = []
    for path, content in files.items():
        classes = re.findall(r"^class (\w+)", content, re.MULTILINE)
        funcs = re.findall(r"^def (\w+)", content, re.MULTILINE)
        lines.append(
            f"{path}: classes={classes}, functions={funcs}"
        )
    return "\n".join(lines)


def _parse_revision_plan(raw: str) -> Tuple[str, str]:
    """Split raw plan into config and code sections."""
    config_match = re.search(
        r"##\s*CONFIG PLAN\s*(.*?)(?=##\s*CODE PLAN|$)", raw, re.DOTALL | re.IGNORECASE
    )
    code_match = re.search(
        r"##\s*CODE PLAN\s*(.*)", raw, re.DOTALL | re.IGNORECASE
    )
    config_plan = config_match.group(1).strip() if config_match else ""
    code_plan = code_match.group(1).strip() if code_match else raw
    return config_plan, code_plan


def _save_iteration(
    output_dir: Path, iteration: int, code: Dict[str, str], record: IterationRecord
) -> None:
    idir = output_dir / f".repro_iterations" / f"iter_{iteration:02d}"
    idir.mkdir(parents=True, exist_ok=True)
    _write_code_files(idir, code)
    summary = {
        "iteration": iteration,
        "n_pass": record.n_pass,
        "n_fail": record.n_fail,
        "all_passed": record.all_passed,
    }
    import json
    (idir / "summary.json").write_text(json.dumps(summary, indent=2))


def _write_code_files(output_dir: Path, files: Dict[str, str]) -> None:
    for rel_path, content in files.items():
        dest = output_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
