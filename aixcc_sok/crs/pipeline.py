"""
AIxCC SoK — Top-Level CRS Pipeline Orchestrator
Paper: https://arxiv.org/abs/2602.07666

§3 — "four CRS capabilities each address a real development moment":
    Full Scan, Delta Scan, SARIF Review, Report Synthesis

§3 Figure 1 — Competition workflow:
    webhook → challenge dispatch → CRS execution → submission to scoring API

This module implements the top-level orchestrator that:
1. Receives a challenge from the competition API
2. Dispatches to the four capability modules
3. Submits results via the competition API
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# §3 — Score ranges and challenge types
# ---------------------------------------------------------------------------

class ScanMode(str, Enum):
    # §3 — "Full Scan: when developers tag a new release, detect and patch vulnerabilities across full codebase"
    FULL = "full_scan"
    # §3 — "Delta Scan: when new code is merged via pull requests, targeted analysis on incremental changes"
    DELTA = "delta_scan"


class SubmissionType(str, Enum):
    # §3 — "Proof of Vulnerability (PoV): an input that triggers abnormal execution"
    POV = "pov"
    # §3 — "Patch: a fix that resolves the vulnerability while preserving functionality"
    PATCH = "patch"
    # §3 — "SARIF assessment: a judgment on whether a SARIF report is valid"
    SARIF = "sarif"
    # §3 — "Bundle: a grouping that links related findings for the same vulnerability"
    BUNDLE = "bundle"


@dataclass
class ScoreRange:
    """§3 — Score range for each submission type."""
    min_score: float
    max_score: float


# §3 — "each submission's weight reflects how much developer time and effort it saves"
SCORE_RANGES: dict[SubmissionType, ScoreRange] = {
    # §3 — "[1, 2] pts"
    SubmissionType.POV: ScoreRange(1.0, 2.0),
    # §3 — "[3, 6] pts"
    SubmissionType.PATCH: ScoreRange(3.0, 6.0),
    # §3 — "[0.5, 1] pt"
    SubmissionType.SARIF: ScoreRange(0.5, 1.0),
    # §3 — "[−7, 7] pts"
    SubmissionType.BUNDLE: ScoreRange(-7.0, 7.0),
}


# ---------------------------------------------------------------------------
# §3 — Challenge and submission data structures
# ---------------------------------------------------------------------------

@dataclass
class Challenge:
    """A single challenge dispatched by the competition API.

    §3 — "Organizers send two kinds of challenges (Full Scan or Delta Scan),
    some accompanied by SARIF broadcasts for review."
    """

    # §3 — unique challenge identifier
    challenge_id: str
    # §3 — challenge project identifier (one of the 53 CPs in the final)
    cp_id: str
    # §3 — challenge project version identifier
    cpv_id: str
    # §3 — full_scan or delta_scan
    scan_mode: ScanMode
    # §3 — path to the challenge project source code
    repo_path: str
    # §3 — OSS-Fuzz harnesses bundled with the challenge
    harness_paths: list[str] = field(default_factory=list)
    # §3 — SARIF reports included for review (may be empty)
    sarif_reports: list[dict[str, Any]] = field(default_factory=list)
    # §3 — duration in seconds (the final ran 142.7h total across 7 phases)
    # [UNSPECIFIED] Per-challenge time limit not stated; using configurable value
    time_limit_seconds: int = 3600
    # §3 — UTC start time for time-decay scoring
    start_time: Optional[float] = None


@dataclass
class Submission:
    """A single scored submission to the competition API."""

    challenge_id: str
    submission_type: SubmissionType
    content: dict[str, Any]
    # §3 — "time-decay grants full points for immediate submissions and half for last-minute ones"
    # [UNSPECIFIED] Exact decay shape; linear approximation from 1.0 to 0.5
    submitted_at: Optional[float] = None


@dataclass
class CRSResult:
    """Aggregated result after processing one challenge."""

    challenge_id: str
    povs: list[dict[str, Any]] = field(default_factory=list)
    patches: list[dict[str, Any]] = field(default_factory=list)
    sarif_assessments: list[dict[str, Any]] = field(default_factory=list)
    bundles: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# §3 — Scoring utilities
# ---------------------------------------------------------------------------

def time_decay_factor(elapsed_seconds: float, total_seconds: float) -> float:
    """§3 — Time-decay multiplier for submissions.

    "full points for immediate submissions and half for last-minute ones"

    [UNSPECIFIED] The exact shape is not given; paper only states two boundary
    conditions: immediate → 1.0, last-minute → 0.5. We use linear interpolation.
    See [9] (competition rulebook) for the authoritative formula.

    Alternatives: step function, exponential decay, competition's actual non-linear curve.
    """
    # Clamp to valid range
    fraction_elapsed = max(0.0, min(1.0, elapsed_seconds / total_seconds))
    # Linear decay: 1.0 at t=0, 0.5 at t=T
    return 1.0 - 0.5 * fraction_elapsed


def accuracy_multiplier(accuracy_rate: float) -> float:
    """§3 — Accuracy multiplier applied to per-challenge totals.

    "non-linear shape that balances technique exploration with practicality:
     high accuracy barely affected (90% → negligible penalty),
     while low accuracy steeply penalized (50% → 6% reduction; 40% → 13% reduction)"

    [UNSPECIFIED] Full formula is in [9] (competition rulebook), not reproduced in paper.
    Piecewise linear approximation from the three data points given:
      (1.00, 1.000), (0.90, ~1.000), (0.50, 0.940), (0.40, 0.870)

    Alternatives: See [9] for authoritative formula.
    """
    if accuracy_rate >= 0.90:
        # §3 — "90% → negligible penalty" — treat as no penalty above 90%
        return 1.0
    elif accuracy_rate >= 0.50:
        # §3 — "50% → 6% reduction" → multiplier = 0.94 at accuracy = 0.50
        # Linear interpolation between (0.90, 1.00) and (0.50, 0.94)
        slope = (0.94 - 1.00) / (0.50 - 0.90)
        return 1.00 + slope * (accuracy_rate - 0.90)
    elif accuracy_rate >= 0.40:
        # §3 — "40% → 13% reduction" → multiplier = 0.87 at accuracy = 0.40
        slope = (0.87 - 0.94) / (0.40 - 0.50)
        return 0.94 + slope * (accuracy_rate - 0.50)
    else:
        # [UNSPECIFIED] Behavior below 40% not described; continue same slope
        slope = (0.87 - 0.94) / (0.40 - 0.50)
        return max(0.0, 0.87 + slope * (accuracy_rate - 0.40))


# ---------------------------------------------------------------------------
# §3 Figure 1 — CRS Orchestrator
# ---------------------------------------------------------------------------

class CRSOrchestrator:
    """§3, Figure 1 — Top-level CRS pipeline orchestrator.

    "triggered by webhook → challenge dispatched → CRS execution → result submitted"

    Coordinates the four capability modules (§3):
        - PoV generation  (§6.1)
        - Patch generation (§6.2)
        - SARIF validation (§6.3)
        - Bundling / Report Synthesis (§6.4)

    Design follows the Buttercup (TB) philosophy (§5):
        "deterministic workflows that decompose challenges into well-defined subtasks,
         with LLMs integrated only where traditional tools fall short"
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        # Lazy import to avoid circular deps; replaced with real modules in Stage 4
        self._pov_module: Any = None
        self._patch_module: Any = None
        self._sarif_module: Any = None
        self._bundler: Any = None

    def attach_modules(
        self,
        pov_module: Any,
        patch_module: Any,
        sarif_module: Any,
        bundler: Any,
    ) -> None:
        """Wire in the four capability modules."""
        self._pov_module = pov_module
        self._patch_module = patch_module
        self._sarif_module = sarif_module
        self._bundler = bundler

    async def process_challenge(self, challenge: Challenge) -> CRSResult:
        """§3 Figure 1 — Main entry point for processing one challenge.

        Runs PoV generation and SARIF validation concurrently, then uses
        discovered PoVs as input to patch generation, then bundles all results.
        """
        result = CRSResult(challenge_id=challenge.challenge_id)

        # §6.1 — PoV generation and §6.3 — SARIF validation run concurrently
        # (independent of each other; SARIF needs only the SARIF reports, not PoVs)
        pov_task = asyncio.create_task(
            self._run_pov_generation(challenge, result)
        )
        sarif_task = asyncio.create_task(
            self._run_sarif_validation(challenge, result)
        )

        await asyncio.gather(pov_task, sarif_task)

        # §6.2 — Patch generation uses discovered PoVs as input
        await self._run_patch_generation(challenge, result)

        # §6.4 — Bundle all findings into coherent vulnerability reports
        await self._run_bundling(challenge, result)

        return result

    async def _run_pov_generation(
        self, challenge: Challenge, result: CRSResult
    ) -> None:
        """§6.1 — PoV generation: fuzzing + LLM pipelines in cooperation."""
        if self._pov_module is None:
            logger.warning("PoV module not attached — skipping PoV generation")
            return
        povs = await self._pov_module.generate(challenge)
        result.povs.extend(povs)
        logger.info(
            "challenge=%s pov_count=%d", challenge.challenge_id, len(povs)
        )

    async def _run_patch_generation(
        self, challenge: Challenge, result: CRSResult
    ) -> None:
        """§6.2 — Patch generation: loop([RCA] → Generate → Validate) → Dedup → Submit."""
        if self._patch_module is None:
            logger.warning("Patch module not attached — skipping patch generation")
            return
        patches = await self._patch_module.generate(challenge, result.povs)
        result.patches.extend(patches)
        logger.info(
            "challenge=%s patch_count=%d", challenge.challenge_id, len(patches)
        )

    async def _run_sarif_validation(
        self, challenge: Challenge, result: CRSResult
    ) -> None:
        """§6.3 — SARIF validation: assess each static analysis report as valid or invalid."""
        if not challenge.sarif_reports:
            return
        if self._sarif_module is None:
            logger.warning("SARIF module not attached — skipping SARIF validation")
            return
        assessments = await self._sarif_module.validate(
            challenge, challenge.sarif_reports
        )
        result.sarif_assessments.extend(assessments)
        logger.info(
            "challenge=%s sarif_assessed=%d",
            challenge.challenge_id, len(assessments),
        )

    async def _run_bundling(
        self, challenge: Challenge, result: CRSResult
    ) -> None:
        """§6.4 — Bundle PoVs, patches, and SARIF assessments into vulnerability reports."""
        if self._bundler is None:
            logger.warning("Bundler not attached — skipping bundling")
            return
        bundles = await self._bundler.bundle(challenge, result)
        result.bundles.extend(bundles)
        logger.info(
            "challenge=%s bundle_count=%d", challenge.challenge_id, len(bundles)
        )
