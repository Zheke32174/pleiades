"""
End-to-end RePro runner.

Ties together supervisory signal extraction and reflective code development.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

from repro.supervisory_signal import (
    Criterion,
    PaperGuide,
    SupervisorySignalPipeline,
)
from repro.code_development import IterationRecord, ReProPipeline


@dataclass
class ReProResult:
    paper_title: str
    n_criteria: int
    iterations_run: int
    final_n_pass: int
    final_n_fail: int
    all_passed: bool
    output_dir: str

    def summary(self) -> str:
        return (
            f"RePro result for '{self.paper_title}'\n"
            f"  Criteria: {self.n_criteria}\n"
            f"  Iterations: {self.iterations_run} / {ReProPipeline.MAX_ITERATIONS}\n"
            f"  Final: {self.final_n_pass} PASS / {self.final_n_fail} FAIL\n"
            f"  All passed: {self.all_passed}\n"
            f"  Output: {self.output_dir}"
        )


def run_repro(
    title: str,
    intro_text: str,
    experiment_text: str,
    paragraphs: List[str],
    output_dir: Path,
) -> ReProResult:
    """
    Full end-to-end RePro pipeline.

    Args:
        title: Paper title.
        intro_text: Abstract + introduction text (for framework guide extraction).
        experiment_text: Experiments/implementation sections (for config extraction).
        paragraphs: All body paragraphs (for level-3 sentence extraction + grounding).
        output_dir: Where to write the reproduced code.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Stage 1: Supervisory Signal Design
    signal_pipeline = SupervisorySignalPipeline(paragraphs)
    fingerprint, guide = signal_pipeline.run(title, intro_text, experiment_text)

    # Save fingerprint
    _save_fingerprint(output_dir, fingerprint)

    # Stage 2: Reflective Code Development
    dev_pipeline = ReProPipeline()
    _, records = dev_pipeline.run(guide, fingerprint, output_dir)

    last = records[-1]
    result = ReProResult(
        paper_title=title,
        n_criteria=len(fingerprint),
        iterations_run=len(records),
        final_n_pass=last.n_pass,
        final_n_fail=last.n_fail,
        all_passed=last.all_passed,
        output_dir=str(output_dir),
    )

    # Save run summary
    (output_dir / "repro_summary.json").write_text(
        json.dumps(asdict(result), indent=2)
    )

    return result


def _save_fingerprint(output_dir: Path, fingerprint: List[Criterion]) -> None:
    data = [{"fact": c.fact, "scope": c.scope, "sources": c.source_sentences}
            for c in fingerprint]
    (output_dir / "fingerprint.json").write_text(json.dumps(data, indent=2))
