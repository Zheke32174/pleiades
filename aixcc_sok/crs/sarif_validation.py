"""
AIxCC SoK — SARIF Validation Module
Paper: https://arxiv.org/abs/2602.07666

§6.3 — "The SARIF validation task requires CRSs to assess each static analysis
report as valid or invalid, submitting a verdict of Correct or Incorrect."

§6.3, Table 5 — Three validation strategies:
    PoV-centric     (AT, TB, FB): match SARIF locations against PoV crash info
    LLM-judge-centric (SP, 42, LC): LLM assesses correctness directly
    Bug-cand-centric (TI): match against bug candidate database

Default: PoV-centric (used by AT=1st, TB=2nd — conservative; Correct only on PoV match).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SARIFVerdict(str, Enum):
    # §6.3 — "Correct": the SARIF report identifies a real vulnerability
    CORRECT = "Correct"
    # §6.3 — "Incorrect": the SARIF report is a false positive
    INCORRECT = "Incorrect"
    # Internal: withhold verdict (no match, no fallback)
    WITHHOLD = "withhold"


@dataclass
class SARIFAssessment:
    """Assessment of a single SARIF report.

    §6.3 — "CRSs can resubmit to revise verdicts while incurring penalties
    in both time and accuracy."
    """

    sarif_report_id: str
    verdict: SARIFVerdict
    # §6.3 — confidence score (used for LLM-judge-centric strategy)
    confidence: float = 0.0
    # Which strategy produced this assessment
    strategy_used: str = "pov_centric"
    # Whether this is a revised verdict (rebsubmission)
    is_revision: bool = False


class SARIFValidationStrategy(ABC):
    """Abstract base for the three SARIF validation strategies (§6.3, Table 5)."""

    @abstractmethod
    async def assess(
        self,
        sarif_report: dict[str, Any],
        context: dict[str, Any],
    ) -> SARIFAssessment:
        """Assess one SARIF report. context contains discovered PoVs, bug candidates, etc."""


class PoVCentricStrategy(SARIFValidationStrategy):
    """§6.3 — PoV-centric: "match SARIF locations against crash information from exploited vulnerabilities."

    Used by AT (1st), TB (2nd), FB (4th).
    "submit Correct only when a match is found and withhold unmatched reports"

    §6.3 — FB additionally uses fallback LLM judgement but only submits Correct from it.
    This is the most conservative strategy: false positives are minimized but recall is lower.
    """

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        use_llm_fallback_correct_only: bool = True,
    ):
        self._llm = llm_client
        # §6.3 — "FB additionally uses fallback LLM judgement, but only submits Correct from it"
        self._llm_fallback = use_llm_fallback_correct_only and llm_client is not None

    async def assess(
        self,
        sarif_report: dict[str, Any],
        context: dict[str, Any],
    ) -> SARIFAssessment:
        """Match SARIF report location against discovered PoV crash stacks."""
        report_id = sarif_report.get("id", "unknown")
        pov_list = context.get("povs", [])

        # §6.3 — "matching SARIF locations against crash information from exploited vulnerabilities"
        matched = self._match_against_povs(sarif_report, pov_list)

        if matched:
            return SARIFAssessment(
                sarif_report_id=report_id,
                verdict=SARIFVerdict.CORRECT,
                confidence=1.0,
                strategy_used="pov_centric",
            )

        # §6.3 — FB fallback: LLM can yield Correct only, never Incorrect
        if self._llm_fallback and self._llm is not None:
            llm_verdict = await self._llm_fallback_assess(sarif_report)
            if llm_verdict == SARIFVerdict.CORRECT:
                return SARIFAssessment(
                    sarif_report_id=report_id,
                    verdict=SARIFVerdict.CORRECT,
                    confidence=0.6,
                    strategy_used="pov_centric+llm_fallback",
                )

        # No match: withhold (don't submit Incorrect — too risky for score)
        return SARIFAssessment(
            sarif_report_id=report_id,
            verdict=SARIFVerdict.WITHHOLD,
            confidence=0.0,
            strategy_used="pov_centric",
        )

    def _match_against_povs(
        self, sarif_report: dict[str, Any], pov_list: list[Any]
    ) -> bool:
        """§6.3 — "Match Any PoV": check if SARIF location overlaps with any PoV crash."""
        sarif_file = sarif_report.get("file_path", "")
        sarif_line = sarif_report.get("line_start", 0)

        for pov in pov_list:
            crash_stack = getattr(pov, "crash_stack", "") or ""
            # Simple heuristic: SARIF file appears in crash stack near stated line
            # TODO: Implement more robust SARIF→crash location matching
            if sarif_file and sarif_file in crash_stack:
                return True
        return False

    async def _llm_fallback_assess(
        self, sarif_report: dict[str, Any]
    ) -> SARIFVerdict:
        """§6.3 — LLM fallback for unmatched SARIF reports (Correct only)."""
        # TODO: Implement LLM assessment prompt
        # Ask: "Is this SARIF report describing a real vulnerability?" → binary yes/no
        raise NotImplementedError("_llm_fallback_assess: implement LLM SARIF assessment")


class LLMJudgeCentricStrategy(SARIFValidationStrategy):
    """§6.3 — LLM-judge-centric: "agentic prompting to directly assess correctness."

    Used by SP (5th), 42 (6th), LC (7th).
    "submitting both Correct and Incorrect based on the model's assessment"
    42 falls back to PoV matching when the model replies with uncertainty.

    Note: This strategy is more aggressive — it will submit Incorrect verdicts,
    which carry penalty risk (§3 — "any incorrect pairing will penalize the entire bundle").
    """

    def __init__(self, llm_client: Any, pov_fallback: bool = True):
        self._llm = llm_client
        # §6.3 — "42 falls back to PoV matching when model replies with uncertainty"
        self._pov_fallback = pov_fallback

    async def assess(
        self,
        sarif_report: dict[str, Any],
        context: dict[str, Any],
    ) -> SARIFAssessment:
        """LLM directly assesses the SARIF report's validity."""
        report_id = sarif_report.get("id", "unknown")

        # §6.3 — LLM-based judgment
        verdict, confidence = await self._llm_judge(sarif_report, context)

        # §6.3 — "42 falls back to PoV matching when the model replies with uncertainty"
        if self._pov_fallback and confidence < 0.5:
            pov_strategy = PoVCentricStrategy(use_llm_fallback_correct_only=False)
            pov_result = await pov_strategy.assess(sarif_report, context)
            if pov_result.verdict != SARIFVerdict.WITHHOLD:
                return SARIFAssessment(
                    sarif_report_id=report_id,
                    verdict=pov_result.verdict,
                    confidence=pov_result.confidence,
                    strategy_used="llm_judge+pov_fallback",
                )

        if confidence < 0.3:
            # [UNSPECIFIED] Confidence threshold for withholding not stated
            # Using 0.3 as conservative threshold to avoid penalty
            return SARIFAssessment(
                sarif_report_id=report_id,
                verdict=SARIFVerdict.WITHHOLD,
                confidence=confidence,
                strategy_used="llm_judge_centric",
            )

        return SARIFAssessment(
            sarif_report_id=report_id,
            verdict=verdict,
            confidence=confidence,
            strategy_used="llm_judge_centric",
        )

    async def _llm_judge(
        self, sarif_report: dict[str, Any], context: dict[str, Any]
    ) -> tuple[SARIFVerdict, float]:
        """LLM assessment of SARIF report validity with confidence score."""
        # TODO: Implement LLM prompt: "Is this SARIF report a true positive?"
        # Include: SARIF file path, CWE ID, code snippet, any available PoV context
        # Return: (Correct|Incorrect, confidence 0.0–1.0)
        raise NotImplementedError("_llm_judge: implement SARIF LLM assessment")


class BugCandCentricStrategy(SARIFValidationStrategy):
    """§6.3 — Bug-candidate-centric (TI only):
    "matching SARIF reports against its bug candidate database,
    initially submitting Incorrect for unmatched reports and revising to Correct on new evidence."

    This is the only strategy that proactively submits Incorrect verdicts from the start.
    [SPECIFIED] TI's behavior: initial Incorrect, revise to Correct on evidence.
    """

    def __init__(self, bug_candidate_db: Optional[list[Any]] = None):
        self._bug_candidates = bug_candidate_db or []

    async def assess(
        self,
        sarif_report: dict[str, Any],
        context: dict[str, Any],
    ) -> SARIFAssessment:
        """Match SARIF report against known bug candidates."""
        report_id = sarif_report.get("id", "unknown")

        matched = self._match_against_candidates(sarif_report)

        if matched:
            return SARIFAssessment(
                sarif_report_id=report_id,
                verdict=SARIFVerdict.CORRECT,
                confidence=0.9,
                strategy_used="bug_cand_centric",
            )

        # §6.3 — TI: "initially submitting Incorrect for unmatched reports"
        # (can revise later when new evidence arrives)
        return SARIFAssessment(
            sarif_report_id=report_id,
            verdict=SARIFVerdict.INCORRECT,
            confidence=0.5,
            strategy_used="bug_cand_centric",
        )

    def _match_against_candidates(self, sarif_report: dict[str, Any]) -> bool:
        """Check if SARIF report location overlaps with any known bug candidate."""
        sarif_file = sarif_report.get("file_path", "")
        sarif_line = sarif_report.get("line_start", 0)

        for candidate in self._bug_candidates:
            if (
                getattr(candidate, "file_path", "") == sarif_file
                and getattr(candidate, "line_start", 0) <= sarif_line
                <= getattr(candidate, "line_end", sarif_line)
            ):
                return True
        return False


class SARIFValidationModule:
    """§6.3 — Top-level SARIF validation module.

    Applies the configured strategy to all SARIF reports in a challenge.
    Default strategy: PoV-centric (AT=1st, TB=2nd).
    """

    STRATEGIES = {
        "pov_centric": PoVCentricStrategy,
        "llm_judge_centric": LLMJudgeCentricStrategy,
        "bug_cand_centric": BugCandCentricStrategy,
    }

    def __init__(self, llm_client: Any, config: dict[str, Any]):
        self._llm = llm_client
        self.config = config
        sarif_cfg = config.get("sarif_validation", {})
        strategy_name = sarif_cfg.get("strategy", "pov_centric")

        if strategy_name == "pov_centric":
            self._strategy = PoVCentricStrategy(
                llm_client=llm_client,
                use_llm_fallback_correct_only=sarif_cfg.get(
                    "llm_fallback_for_correct", True
                ),
            )
        elif strategy_name == "llm_judge_centric":
            self._strategy = LLMJudgeCentricStrategy(llm_client=llm_client)
        elif strategy_name == "bug_cand_centric":
            self._strategy = BugCandCentricStrategy()
        else:
            raise ValueError(f"Unknown SARIF strategy: {strategy_name!r}")

    async def validate(
        self, challenge: Any, sarif_reports: list[dict[str, Any]]
    ) -> list[SARIFAssessment]:
        """§6.3 — Assess all SARIF reports for a challenge.

        §6.3 — "CRSs can resubmit to revise verdicts while incurring penalties"
        This implementation does a single pass; revision logic is in the orchestrator.
        """
        assessments: list[SARIFAssessment] = []
        context = {"povs": [], "challenge": challenge}  # povs filled in by orchestrator

        for report in sarif_reports:
            assessment = await self._strategy.assess(report, context)
            # §6.3 — only submit non-withheld verdicts
            if assessment.verdict != SARIFVerdict.WITHHOLD:
                assessments.append(assessment)
            else:
                logger.debug("Withholding SARIF verdict for report %s", report.get("id"))

        logger.info(
            "SARIF validation: %d reports → %d submitted (strategy=%s)",
            len(sarif_reports), len(assessments),
            self.config.get("sarif_validation", {}).get("strategy", "pov_centric"),
        )
        return assessments
