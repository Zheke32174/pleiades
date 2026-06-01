"""
AIxCC SoK — Patch Generation Module
Paper: https://arxiv.org/abs/2602.07666

§6.2 — "All CRSs follow a de facto patch pipeline":
    loop([RCA] → Generate → Validate) → Dedup → Submit

§6.2 — Agent architecture patterns (three variants):
    Multi-Arch   (AT=1st, SP=5th): ensemble of diverse patcher agents
    Multi-Agent  (TB=2nd, TI=3rd): coordinating sub-agents in pipeline/hierarchy
    Single-Agent (FB=4th, 42=6th, LC=7th): single agent with configuration diversity

Default: Multi-Agent (TB=2nd place — best simplicity/performance tradeoff).
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# §6.2 — Patch data structure
# ---------------------------------------------------------------------------

@dataclass
class Patch:
    """A candidate fix for a vulnerability.

    §3 — "a fix that resolves the vulnerability while preserving functionality"
    """

    patch_id: str
    # §6.2 — unified diff or file content
    diff: str
    # §6.2 — the PoV(s) that triggered this vulnerability (used for validation)
    source_pov_ids: list[str] = field(default_factory=list)
    # §6.2 — root cause analysis result that informed this patch
    rca_summary: Optional[str] = None
    # §6.2 — validation status: "unvalidated", "valid", "invalid"
    validation_status: str = "unvalidated"
    # §6.2 — LLM reflection notes from failed prior attempts
    reflection_notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# §6.2 — Root Cause Analysis
# ---------------------------------------------------------------------------

class RCAAgent:
    """§6.2 — Standalone Root Cause Analysis component.

    "AT, TB, TI, SP implement standalone RCA components, allowing LLMs to
    separately focus on root cause analysis and patch synthesis as distinct sub-problems."

    "TB, TI, SP leverage information from multiple PoVs for more accurate RCA."

    §6.2 — SP additionally incorporates a non-LLM RCA combining multi-source signals
    (SAST reports, stack traces, fuzzing invariants) with weighted voting.
    [UNSPECIFIED] Vote weights for non-LLM RCA — using equal weighting as default.
    """

    def __init__(self, llm_client: Any, config: dict[str, Any]):
        self._llm = llm_client
        self.config = config

    async def analyze(
        self,
        pov_list: list[Any],
        repo_path: str,
        sast_results: Optional[list[dict[str, Any]]] = None,
    ) -> str:
        """Perform root cause analysis using PoVs and optional SAST results.

        §6.2 — "TB, TI, SP leverage information from multiple PoVs"
        §6.2 — Information sources: crash/sanitizer output, call paths, coverage, debugger

        Args:
            pov_list: One or more PoVs showing the vulnerability
            repo_path: Challenge project source
            sast_results: Optional SAST reports for non-LLM RCA signal

        Returns:
            Natural-language root cause summary for use in patch generation
        """
        # TODO: Build RCA prompt with all PoV crash traces
        # TODO: Include SAST results if non_llm_rca=True (SP's weighted voting approach)
        # TODO: Optionally call GDB/JDB for dynamic info (4 teams used runtime probes)
        raise NotImplementedError("RCAAgent.analyze: implement multi-PoV RCA prompt")


# ---------------------------------------------------------------------------
# §6.2 — Patch Validator
# ---------------------------------------------------------------------------

class PatchValidator:
    """§6.2 — Multi-layer validation before accepting a candidate patch.

    "CRSs employ several checks within each iteration":
    1. Basic Checks: build verification (all teams)
    2. PoV Test (Gen): reproduction during generation (all teams)
    3. Project Tests: project test suites (all teams except 42)
    4. PoV Test (Submit): revalidate against broader PoV set before submission
    5. LLM-as-Judge: optional LLM evaluation (3/7 teams)
    6. Post-patch Fuzz: short-term fuzzing on patched project (FB, SP)
    """

    def __init__(self, llm_client: Any, config: dict[str, Any]):
        self._llm = llm_client
        self.config = config
        val_cfg = config.get("patch_generation", {}).get("validation", {})
        # §6.2 — validation flags from config
        self._run_project_tests = val_cfg.get("run_project_tests", True)
        self._pov_count_gen = val_cfg.get("pov_count_during_gen", 1)
        self._pov_count_submit = val_cfg.get("pov_count_before_submit", -1)
        self._llm_as_judge = val_cfg.get("llm_as_judge", False)
        self._post_patch_fuzz = val_cfg.get("post_patch_fuzz", False)

    async def validate_during_generation(
        self, patch: Patch, repo_path: str, pov_list: list[Any]
    ) -> bool:
        """§6.2 — Fast validation loop during patch generation.

        Uses a subset of PoVs (keep iteration loop fast).
        [UNSPECIFIED] Subset size: default=1 PoV (from config pov_count_during_gen)
        TB uses N, AT and FB use 1.
        """
        # §6.2 — Check 1: Build verification (all teams)
        if not await self._check_build(patch, repo_path):
            return False

        # §6.2 — Check 2: PoV reproduction
        subset = (
            pov_list[:self._pov_count_gen]
            if self._pov_count_gen > 0
            else pov_list
        )
        if not await self._check_pov_reproduction(patch, repo_path, subset):
            return False

        # §6.2 — Check 3: Project tests (all teams except 42)
        if self._run_project_tests:
            if not await self._check_project_tests(patch, repo_path):
                return False

        return True

    async def validate_before_submission(
        self, patch: Patch, repo_path: str, all_povs: list[Any]
    ) -> bool:
        """§6.2 — Final validation against all PoVs before submission.

        "before submission, most CRSs revalidate patches against a broader PoV
        set than was used during generation, catching incomplete fixes"

        §6.2 — pov_count_before_submit: -1 = all PoVs (AT, FB → *, TB → N, LC → 1)
        """
        pov_subset = (
            all_povs
            if self._pov_count_submit == -1
            else all_povs[:self._pov_count_submit]
        )

        if not await self._check_pov_reproduction(patch, repo_path, pov_subset):
            return False

        # §6.2 — Optional: LLM-as-Judge (3/7 teams: AT, FB, SP)
        if self._llm_as_judge:
            if not await self._llm_judge(patch, all_povs):
                return False

        # §6.2 — Optional: Post-patch fuzzing for incomplete patch detection (FB, SP)
        if self._post_patch_fuzz:
            if not await self._post_patch_fuzz_check(patch, repo_path):
                return False

        return True

    async def _check_build(self, patch: Patch, repo_path: str) -> bool:
        """§6.2 — "build verification" (all teams)."""
        # TODO: Apply patch, attempt build, return success/failure
        raise NotImplementedError("_check_build: implement patch application + build")

    async def _check_pov_reproduction(
        self, patch: Patch, repo_path: str, pov_subset: list[Any]
    ) -> bool:
        """§6.2 — "PoV reproduction": patch must still trigger original bugs before fixing."""
        # TODO: Apply patch, run each PoV, verify crash is resolved (sanitizer clean)
        raise NotImplementedError("_check_pov_reproduction: implement PoV re-execution")

    async def _check_project_tests(self, patch: Patch, repo_path: str) -> bool:
        """§6.2 — "project test suites" (42 skips project tests)."""
        # TODO: Run project's test suite (e.g., make test, pytest, mvn test)
        raise NotImplementedError("_check_project_tests: implement test suite runner")

    async def _llm_judge(self, patch: Patch, all_povs: list[Any]) -> bool:
        """§6.2 — LLM-as-Judge evaluation.

        "judging whether patches correctly address the root cause (AT)
         and self-reflecting on whether patches genuinely fix vulnerabilities
         rather than being superficial, easily-bypassed, or having side effects (FB/SP)"
        """
        # TODO: Implement LLM evaluation prompt
        raise NotImplementedError("_llm_judge: implement LLM patch evaluation prompt")

    async def _post_patch_fuzz_check(
        self, patch: Patch, repo_path: str
    ) -> bool:
        """§6.2 — "FB and SP adopt short-term fuzzing on patched projects for incomplete patch detection"."""
        # TODO: Run fuzzer for short duration on patched project, check for new crashes
        raise NotImplementedError("_post_patch_fuzz_check: implement short-term fuzzing")


# ---------------------------------------------------------------------------
# §6.2 — Minimal Patch Set Calculator
# ---------------------------------------------------------------------------

class MinimalPatchSetCalculator:
    """§6.2 — Computes a minimal patch set that covers all known PoVs.

    "Four CRSs (AT, TB, SP, 42) leverage the fact that a single patch can fix
    multiple PoVs sharing the same root cause, and compute a minimal patch set
    that covers all known PoVs to avoid duplicate submissions."

    §6.2 — Timing: "on each new PoV (AT, TB, SP) for faster response"
    §6.2 — Mode: "recompute over all PoVs (TB, SP) for better optimization" [SPECIFIED default]

    The minimal set cover is an NP-hard problem; greedy approximation is standard
    but [UNSPECIFIED] whether teams used exact cover or greedy approximation.
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        dedup_cfg = config.get("patch_generation", {}).get("dedup_and_submit", {})
        self._recompute_mode = dedup_cfg.get("patch_set_mode", "full_recompute")

    def compute(
        self,
        patches: list[Patch],
        all_pov_ids: list[str],
    ) -> list[Patch]:
        """Greedy set cover: select minimum patches that cover all PoV IDs.

        §6.2 — "a single patch can fix multiple PoVs sharing the same root cause"

        [UNSPECIFIED] Whether greedy or exact cover is used. Greedy chosen here
        (standard approximation algorithm, O(n log n), optimal for most practical cases).
        Alternatives: exact ILP solver (expensive), random restarts.
        """
        uncovered = set(all_pov_ids)
        selected: list[Patch] = []

        # Build a copy to avoid mutating input
        remaining = list(patches)

        while uncovered and remaining:
            # Greedy: pick the patch covering the most uncovered PoVs
            best = max(
                remaining,
                key=lambda p: len(set(p.source_pov_ids) & uncovered),
            )
            if not set(best.source_pov_ids) & uncovered:
                break
            selected.append(best)
            uncovered -= set(best.source_pov_ids)
            remaining.remove(best)

        return selected


# ---------------------------------------------------------------------------
# §6.2 — Patch Generation Agents (Multi-Agent default)
# ---------------------------------------------------------------------------

class MultiAgentPatcher(ABC):
    """§6.2 — Multi-Agent architecture: "a single patcher contains multiple coordinating sub-agents."

    TB's 4-agent pipeline: RCA → fix strategy → patch creation → reflection
    TI's hierarchical: ReAct outer loop with SourceQuestionsAgent as inner tool

    Default: TB-style pipeline (2nd place, clean decomposition).
    """

    def __init__(self, llm_client: Any, config: dict[str, Any]):
        self._llm = llm_client
        self.config = config
        gen_cfg = config.get("patch_generation", {}).get("generation", {})
        self._use_llm_reflection = gen_cfg.get("llm_reflection", True)
        # [UNSPECIFIED] Max iterations not stated in paper
        self._max_iterations = config.get(
            "patch_generation", {}
        ).get("agent_architecture", {}).get("max_iterations", 10)

    @abstractmethod
    async def generate_patch(
        self,
        rca_summary: str,
        pov_list: list[Any],
        repo_path: str,
        prior_failures: Optional[list[str]] = None,
    ) -> Optional[Patch]:
        """Generate one candidate patch given RCA and PoV context."""

    async def patch_loop(
        self,
        rca: RCAAgent,
        validator: PatchValidator,
        pov_list: list[Any],
        repo_path: str,
    ) -> list[Patch]:
        """§6.2 — "loop([RCA] → Generate → Validate)".

        Runs until a valid patch is found or max_iterations is reached.
        """
        rca_summary = await rca.analyze(pov_list, repo_path)
        valid_patches: list[Patch] = []
        reflection_notes: list[str] = []

        for iteration in range(self._max_iterations):
            candidate = await self.generate_patch(
                rca_summary=rca_summary,
                pov_list=pov_list,
                repo_path=repo_path,
                prior_failures=reflection_notes if self._use_llm_reflection else None,
            )
            if candidate is None:
                logger.debug("Patch generation returned None at iteration %d", iteration)
                break

            is_valid = await validator.validate_during_generation(
                candidate, repo_path, pov_list
            )

            if is_valid:
                valid_patches.append(candidate)
                logger.info("Valid patch found at iteration %d", iteration)
                break
            else:
                # §6.2 — LLM reflection: "enables agents to learn from failed attempts"
                if self._use_llm_reflection:
                    note = await self._reflect_on_failure(candidate, pov_list)
                    reflection_notes.append(note)
                    candidate.reflection_notes.append(note)

        return valid_patches

    async def _reflect_on_failure(
        self, failed_patch: Patch, pov_list: list[Any]
    ) -> str:
        """§6.2 — "dedicated reflection agent that analyzes failures at each generation step."

        TB's implementation: separate reflection agent → corrective guidance.
        """
        # TODO: Implement reflection prompt
        # Include: failed patch diff, build/test error message, prior RCA
        raise NotImplementedError("_reflect_on_failure: implement LLM reflection prompt")


class TBStyleMultiAgentPatcher(MultiAgentPatcher):
    """§6.2 — Buttercup (TB) Multi-Agent patcher.

    "TB organizes its four agents into a pipeline of RCA, fix strategy,
    patch creation, and reflection, each handing off to the next."

    Default implementation. TB was 2nd place overall, best simplicity/performance ratio.
    """

    async def generate_patch(
        self,
        rca_summary: str,
        pov_list: list[Any],
        repo_path: str,
        prior_failures: Optional[list[str]] = None,
    ) -> Optional[Patch]:
        """TB 4-step pipeline: fix-strategy → patch-creation (RCA already done upstream)."""
        # Step 1: Fix strategy agent — decide what kind of fix to apply
        fix_strategy = await self._fix_strategy_agent(rca_summary, prior_failures)
        if not fix_strategy:
            return None

        # Step 2: Patch creation agent — generate the actual diff
        patch_diff = await self._patch_creation_agent(
            rca_summary, fix_strategy, repo_path, pov_list
        )
        if not patch_diff:
            return None

        import hashlib, time
        patch_id = hashlib.sha256(f"{time.time()}:{patch_diff}".encode()).hexdigest()[:16]
        return Patch(
            patch_id=patch_id,
            diff=patch_diff,
            source_pov_ids=[getattr(p, "pov_id", str(i)) for i, p in enumerate(pov_list)],
            rca_summary=rca_summary,
        )

    async def _fix_strategy_agent(
        self,
        rca_summary: str,
        prior_failures: Optional[list[str]],
    ) -> Optional[str]:
        """§6.2 — "fix strategy" agent in TB's pipeline."""
        # TODO: Prompt LLM to decide fix strategy (bounds check, null check, ownership fix, etc.)
        raise NotImplementedError("_fix_strategy_agent: implement fix strategy LLM prompt")

    async def _patch_creation_agent(
        self,
        rca_summary: str,
        fix_strategy: str,
        repo_path: str,
        pov_list: list[Any],
    ) -> Optional[str]:
        """§6.2 — "patch creation" agent: generates unified diff."""
        # TODO: Prompt LLM with rca+fix_strategy+repo context to generate patch diff
        # Include: code indexer results, SAST findings, PoV bytes if use_pov_bytes=True
        raise NotImplementedError("_patch_creation_agent: implement patch creation LLM prompt")


# ---------------------------------------------------------------------------
# §6.2 — Top-level Patch Generation Module
# ---------------------------------------------------------------------------

class PatchGenerationModule:
    """§6.2 — Coordinates the full patch pipeline for one challenge.

    Pipeline: identify PoVs → RCA → Generate → Validate → Dedup → Submit
    """

    def __init__(
        self,
        patcher: MultiAgentPatcher,
        rca: RCAAgent,
        validator: PatchValidator,
        patch_set_calc: MinimalPatchSetCalculator,
        config: dict[str, Any],
    ):
        self._patcher = patcher
        self._rca = rca
        self._validator = validator
        self._calc = patch_set_calc
        self.config = config
        dedup_cfg = config.get("patch_generation", {}).get("dedup_and_submit", {})
        self._submit_delay = dedup_cfg.get("submit_delay_minutes", 0)

    async def generate(
        self, challenge: Any, pov_list: list[Any]
    ) -> list[Patch]:
        """§6.2 — Full patch pipeline for a challenge.

        Args:
            challenge: Challenge object with repo_path and challenge_id
            pov_list: PoVs discovered during PoV generation phase

        Returns:
            Minimal set of validated patches ready for submission
        """
        if not pov_list:
            logger.info(
                "No PoVs for challenge %s — skipping PoV-based patching",
                challenge.challenge_id,
            )
            return []

        # §6.2 — "loop([RCA] → Generate → Validate)" for each PoV group
        all_valid_patches: list[Patch] = await self._patcher.patch_loop(
            rca=self._rca,
            validator=self._validator,
            pov_list=pov_list,
            repo_path=challenge.repo_path,
        )

        if not all_valid_patches:
            logger.info(
                "No valid patches found for challenge %s", challenge.challenge_id
            )
            return []

        # §6.2 — Final validation against all PoVs before submission
        final_patches: list[Patch] = []
        pov_ids = [getattr(p, "pov_id", str(i)) for i, p in enumerate(pov_list)]
        for patch in all_valid_patches:
            if await self._validator.validate_before_submission(
                patch, challenge.repo_path, pov_list
            ):
                patch.validation_status = "valid"
                final_patches.append(patch)

        # §6.2 — "four CRSs compute a minimal patch set that covers all known PoVs"
        minimal_set = self._calc.compute(final_patches, pov_ids)

        logger.info(
            "challenge=%s valid_patches=%d minimal_set=%d",
            challenge.challenge_id, len(final_patches), len(minimal_set),
        )

        # §6.2 — Submit delay (0 = immediate; SP used ≥60min delay)
        if self._submit_delay > 0:
            logger.info(
                "Delaying patch submission by %d minutes (configured)", self._submit_delay
            )
            await asyncio.sleep(self._submit_delay * 60)

        return minimal_set
