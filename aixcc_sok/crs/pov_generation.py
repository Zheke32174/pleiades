"""
AIxCC SoK — PoV Generation Module
Paper: https://arxiv.org/abs/2602.07666

§6.1 — "Two complementary discovery pipelines emerge":
    1. Fuzzing Pipeline — extends traditional fuzzing with LLM-assisted components
    2. LLM-Based PoV Generation Pipeline — directly leverages LLMs to identify vulnerabilities

§6.1 — Pipeline Cooperation (bidirectional):
    "LLM PoV Gen → Fuzz (5 teams): successful/failed/intermediate results shared with fuzzers"
    "Fuzz → LLM PoV Gen (3 teams): coverage info + reached-but-unexploited inputs forwarded"

§6.1 — PoV Submission:
    "All teams adopt straightforward strategies: submit unique PoVs as soon as possible"
    "deduplication using crash stack traces, input hashing, sanitizer signatures"
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# §6.1 — PoV data structure
# ---------------------------------------------------------------------------

@dataclass
class PoV:
    """A Proof of Vulnerability: an input that triggers abnormal execution.

    §3 — "an input that triggers abnormal execution (e.g., a crash)"
    """

    # Unique identifier for this PoV
    pov_id: str
    # §6.1 — the fuzzer input bytes or the Python generator script
    input_bytes: bytes
    # §6.1 — crash stack trace from sanitizer output (used for deduplication)
    crash_stack: Optional[str] = None
    # §6.1 — sanitizer signature (ASan/UBSan/etc.)
    sanitizer_signature: Optional[str] = None
    # §6.1 — CWE classification if known
    cwe_id: Optional[str] = None
    # §6.1 — which pipeline produced this PoV ("fuzzing" or "llm")
    source: str = "fuzzing"
    # §6.1 — coverage information for Fuzz→LLM cooperation
    coverage_info: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# §6.1 — Deduplication
# ---------------------------------------------------------------------------

class PoVDeduplicator:
    """§6.1 — Deduplication using crash stack traces, input hashing, sanitizer signatures.

    "all teams implement deduplication using crash stack traces, input hashing,
    sanitizer signatures, etc."

    [UNSPECIFIED] Which deduplication method takes priority when multiple signals
    disagree. We apply stack-trace first, then sanitizer signature, then input hash.

    Optional: LLM semantic deduplication (used by TI and FB):
    "TI and FB further use LLMs to group semantically equivalent PoVs"
    This is disabled by default (llm_semantic_dedup=False in config).
    """

    def __init__(self, use_llm_dedup: bool = False):
        # §6.1 — default: lightweight dedup only
        self._use_llm_dedup = use_llm_dedup
        self._seen_stack_hashes: set[str] = set()
        self._seen_input_hashes: set[str] = set()
        self._seen_sanitizer_sigs: set[str] = set()

    def is_duplicate(self, pov: PoV) -> bool:
        """Return True if this PoV is a duplicate of a previously seen PoV."""
        # §6.1 — crash stack trace deduplication
        if pov.crash_stack:
            stack_hash = hashlib.sha256(pov.crash_stack.encode()).hexdigest()
            if stack_hash in self._seen_stack_hashes:
                return True

        # §6.1 — sanitizer signature deduplication
        if pov.sanitizer_signature:
            if pov.sanitizer_signature in self._seen_sanitizer_sigs:
                return True

        # §6.1 — input hash deduplication (fallback)
        input_hash = hashlib.sha256(pov.input_bytes).hexdigest()
        if input_hash in self._seen_input_hashes:
            return True

        return False

    def register(self, pov: PoV) -> None:
        """Mark a PoV as seen so future duplicates are caught."""
        if pov.crash_stack:
            self._seen_stack_hashes.add(
                hashlib.sha256(pov.crash_stack.encode()).hexdigest()
            )
        if pov.sanitizer_signature:
            self._seen_sanitizer_sigs.add(pov.sanitizer_signature)
        self._seen_input_hashes.add(hashlib.sha256(pov.input_bytes).hexdigest())


# ---------------------------------------------------------------------------
# §6.1 — Fuzzing Pipeline
# ---------------------------------------------------------------------------

class FuzzingPipeline(ABC):
    """§6.1 — Fuzzing Pipeline: extends traditional fuzzing with LLM-assisted components.

    Concrete integrations implement this interface for specific fuzzers
    (AFL++, libAFL, OSS-Fuzz harnesses, etc.).

    §6.1 — all teams run OSS-Fuzz as baseline; custom enhancements are additive.
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._cooperation_queue: asyncio.Queue[PoV] = asyncio.Queue()

    @abstractmethod
    async def run(
        self,
        repo_path: str,
        harness_paths: list[str],
        seed_corpus: list[bytes],
        time_limit_seconds: int,
    ) -> list[PoV]:
        """Run the fuzzing pipeline and return discovered PoVs."""

    async def receive_from_llm(self, pov: PoV) -> None:
        """§6.1 — Cooperation: receive LLM-generated PoVs/seeds to extend fuzzing.

        "LLM PoV Gen→Fuzz (five teams): successful, failed, and intermediate
        results from LLM PoV generation are shared with fuzzers"
        """
        await self._cooperation_queue.put(pov)

    async def send_to_llm_pipeline(self) -> Optional[PoV]:
        """§6.1 — Cooperation: send reached-but-unexploited inputs to LLM pipeline.

        "Fuzz→LLM PoV Gen (three teams: AT, TI, SP): coverage information to
        guide LLM generation; reached-but-unexploited inputs forwarded for exploitation"
        """
        try:
            return self._cooperation_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None


class OSSFuzzFuzzingPipeline(FuzzingPipeline):
    """§6.1 — Concrete fuzzing pipeline wrapping OSS-Fuzz infrastructure.

    "Organizers adopted OSS-Fuzz" as the baseline harness framework (§3).

    TODO: Implement actual fuzzer invocation.
    The scaffold shows the interface; replace with real subprocess calls to
    AFL++, libFuzzer, or other supported fuzzers.
    """

    async def run(
        self,
        repo_path: str,
        harness_paths: list[str],
        seed_corpus: list[bytes],
        time_limit_seconds: int,
    ) -> list[PoV]:
        logger.info(
            "OSSFuzz fuzzing: repo=%s harnesses=%d seeds=%d time=%ds",
            repo_path, len(harness_paths), len(seed_corpus), time_limit_seconds,
        )
        # TODO: Implement subprocess call to OSS-Fuzz runner
        # TODO: Parse crash outputs into PoV objects with crash_stack and sanitizer_signature
        return []


# ---------------------------------------------------------------------------
# §6.1 — Seed Generation Agent
# ---------------------------------------------------------------------------

class SeedGenerationAgent:
    """§6.1 — LLM-based seed generation agent.

    "Six teams use LLMs to generate seeds in two scenarios:
    early-stage bootstrap (analyzing harness code for input formats) and
    troubleshooting (generating inputs for coverage blockers)"

    "all teams chose to have LLMs generate Python scripts that produce
    inputs upon execution" — [SPECIFIED] Output format is Python scripts.

    §6.1 — Agents typically incorporate conventional program analysis tools.
    """

    def __init__(self, llm_client: Any, config: dict[str, Any]):
        self._llm = llm_client
        self.config = config

    async def generate_seed_scripts(
        self,
        harness_code: str,
        coverage_blockers: Optional[list[str]] = None,
    ) -> list[str]:
        """Generate Python scripts that produce fuzzer seed inputs.

        §6.1 — "LLMs generate Python scripts that produce inputs upon execution"
        §6.1 — "analyzing harness code for input formats"

        Args:
            harness_code: Source code of the fuzzing harness
            coverage_blockers: Optional list of coverage-blocking conditions to target

        Returns:
            List of Python script strings; each script produces seed bytes when run
        """
        # TODO: Implement LLM prompt for seed generation
        # Include: harness analysis, input format detection, coverage target if provided
        raise NotImplementedError(
            "SeedGenerationAgent.generate_seed_scripts: "
            "implement LLM prompt using harness_code and coverage_blockers"
        )


# ---------------------------------------------------------------------------
# §6.1 — Bug Candidate Identification
# ---------------------------------------------------------------------------

@dataclass
class BugCandidate:
    """A potential vulnerability location identified by static analysis + LLM.

    §6.1 — "Five teams build agent systems combining LLMs, static analysis tools
    (CodeQL, Semgrep, Infer), and predefined sink lists to identify and filter candidates."
    """

    candidate_id: str
    # §6.1 — file path and line range of the suspected vulnerability
    file_path: str
    line_start: int
    line_end: int
    # §6.1 — CWE classification (CWE-ID or None)
    cwe_id: Optional[str] = None
    # §6.1 — confidence score from weighted vote aggregation
    # [UNSPECIFIED] Vote weights not specified; equal weighting used as default
    confidence: float = 0.0
    # §6.1 — which tools flagged this candidate (CodeQL, Semgrep, Infer, sink_list, LLM)
    flagged_by: list[str] = field(default_factory=list)


class BugCandidateIdentifier:
    """§6.1 — Identifies and filters bug candidates using static analysis + LLM.

    "SP and LC aggregate weighted votes across multiple tools and LLMs to rank candidates"
    "TI uses LLM logprobs as a token-efficient confidence signal"

    [UNSPECIFIED] Vote weights. Default: equal weight (1.0 per tool/LLM).
    Alternatives: learned weights, logprob-based (TI), empirically tuned.
    """

    def __init__(self, llm_client: Any, config: dict[str, Any]):
        self._llm = llm_client
        self.config = config
        # §6.1 — "predefined sink lists" used by teams
        # TODO: Populate with CWE-specific dangerous sinks (strcpy, memcpy, free, etc.)
        self._sink_list: list[str] = []

    async def identify(
        self,
        repo_path: str,
        sast_results: Optional[list[dict[str, Any]]] = None,
    ) -> list[BugCandidate]:
        """Run multi-tool candidate identification and return ranked candidates.

        §6.1 — Tools: CodeQL, Semgrep, Infer, predefined sink lists, LLM
        §6.1 — "aggregate weighted votes across multiple tools and LLMs to rank candidates"

        Args:
            repo_path: Path to the challenge project source
            sast_results: Pre-computed SAST outputs (CodeQL/Semgrep/Infer JSON)

        Returns:
            Ranked list of BugCandidates (highest confidence first)
        """
        candidates: list[BugCandidate] = []

        # TODO: Run CodeQL if available
        # TODO: Run Semgrep if available
        # TODO: Run Infer if available
        # TODO: Match against sink list
        # TODO: LLM-based candidate identification
        # TODO: Aggregate votes and compute confidence
        # TODO: Sort by confidence descending

        return sorted(candidates, key=lambda c: c.confidence, reverse=True)


# ---------------------------------------------------------------------------
# §6.1 — LLM-Based PoV Generation Pipeline (Reach + Exploit)
# ---------------------------------------------------------------------------

class LLMPoVGenerationAgent:
    """§6.1 — LLM-based PoV generation agent (two-phase: reach → exploit).

    "Three (AT, TI, SP) further decompose generation:
     a reach agent drives execution to the target sink,
     and an exploit agent crafts the trigger."

    §6.1 — Agents receive: source code, call paths, coverage, runtime logs,
    debugger access (GDB/JDB).

    §6.1 — "Four teams inject CWE-specific guidance" (AT, TB, FB, SP).
    """

    def __init__(self, llm_client: Any, config: dict[str, Any]):
        self._llm = llm_client
        self.config = config
        # §6.1 — "all teams chose to have LLMs generate Python scripts"
        self._output_as_scripts = config.get("pov_generation", {}).get(
            "llm_pipeline", {}
        ).get("seed_gen_as_scripts", True)

    async def generate(
        self,
        candidate: BugCandidate,
        repo_path: str,
        cwe_guidance: Optional[str] = None,
        coverage_info: Optional[dict[str, Any]] = None,
    ) -> list[PoV]:
        """Generate PoVs for a specific bug candidate.

        §6.1 — Two-phase reach→exploit if two_phase_generation=True.
        §6.1 — "four teams inject CWE-specific guidance to steer exploit construction"

        Args:
            candidate: Bug candidate to target
            repo_path: Source code location
            cwe_guidance: CWE-specific exploitation knowledge (optional)
            coverage_info: Coverage data from fuzzer cooperation (optional)

        Returns:
            List of PoVs (may be empty if generation fails)
        """
        povs: list[PoV] = []

        # §6.1 — Phase 1: Reach — drive execution to the vulnerable sink
        if self.config.get("pov_generation", {}).get("llm_pipeline", {}).get(
            "two_phase_generation", True
        ):
            reachable = await self._reach_phase(candidate, repo_path, coverage_info)
            if not reachable:
                logger.debug(
                    "Reach phase failed for candidate %s", candidate.candidate_id
                )
                return []
            # §6.1 — Phase 2: Exploit — craft input that triggers the bug
            povs = await self._exploit_phase(candidate, repo_path, cwe_guidance)
        else:
            # Single-phase: combine reach+exploit in one LLM call
            povs = await self._single_phase_generate(
                candidate, repo_path, cwe_guidance
            )

        return povs

    async def _reach_phase(
        self,
        candidate: BugCandidate,
        repo_path: str,
        coverage_info: Optional[dict[str, Any]],
    ) -> bool:
        """§6.1 — "reach agent drives execution to the target sink"."""
        # TODO: Implement reach agent LLM prompt
        # Include: candidate location, call graph paths, coverage data
        raise NotImplementedError("_reach_phase: implement LLM reach agent")

    async def _exploit_phase(
        self,
        candidate: BugCandidate,
        repo_path: str,
        cwe_guidance: Optional[str],
    ) -> list[PoV]:
        """§6.1 — "exploit agent crafts the trigger"."""
        # TODO: Implement exploit agent LLM prompt
        # Include: CWE guidance if available, reached execution path from _reach_phase
        raise NotImplementedError("_exploit_phase: implement LLM exploit agent")

    async def _single_phase_generate(
        self,
        candidate: BugCandidate,
        repo_path: str,
        cwe_guidance: Optional[str],
    ) -> list[PoV]:
        """Single-phase PoV generation (used when two_phase_generation=False)."""
        # TODO: Implement single-phase LLM PoV generation prompt
        raise NotImplementedError("_single_phase_generate: implement single-phase PoV agent")


# ---------------------------------------------------------------------------
# §6.1 — Top-level PoV Generation Module (both pipelines + cooperation)
# ---------------------------------------------------------------------------

class PoVGenerationModule:
    """§6.1 — Coordinates fuzzing and LLM pipelines with bidirectional cooperation.

    "Both pipelines reinforce each other: fuzzing supplies coverage and inputs to
    LLM-based generation, while LLM-generated outputs (even failures) seed fuzzers."

    Architecture: Atlantis/Buttercup consensus (top-2 teams both ran cooperation).
    """

    def __init__(
        self,
        fuzzing_pipeline: FuzzingPipeline,
        llm_agent: LLMPoVGenerationAgent,
        seed_agent: SeedGenerationAgent,
        candidate_identifier: BugCandidateIdentifier,
        config: dict[str, Any],
    ):
        self._fuzzer = fuzzing_pipeline
        self._llm_agent = llm_agent
        self._seed_agent = seed_agent
        self._candidate_id = candidate_identifier
        self.config = config
        self._deduplicator = PoVDeduplicator(
            use_llm_dedup=config.get("pov_generation", {})
            .get("submission", {})
            .get("llm_semantic_dedup", False)
        )

    async def generate(self, challenge: Any) -> list[PoV]:
        """Run both pipelines concurrently and return deduplicated PoVs.

        §6.1 — "Five teams explored both pipelines"
        §6.1 — "Both pipelines reinforce each other"
        """
        coop_cfg = self.config.get("pov_generation", {}).get("cooperation", {})
        llm_to_fuzz = coop_cfg.get("llm_to_fuzz", True)
        fuzz_to_llm = coop_cfg.get("fuzz_to_llm", True)

        # Generate seeds for fuzzer bootstrapping
        # §6.1 — "Six teams use LLMs to generate seeds ... early-stage bootstrap"
        seed_corpus = await self._bootstrap_seeds(challenge)

        # Run pipelines concurrently
        fuzzing_task = asyncio.create_task(
            self._run_fuzzing_pipeline(challenge, seed_corpus, fuzz_to_llm)
        )
        llm_task = asyncio.create_task(
            self._run_llm_pipeline(challenge, llm_to_fuzz)
        )

        fuzzing_povs, llm_povs = await asyncio.gather(fuzzing_task, llm_task)

        # §6.1 — "submit unique PoVs as soon as possible" — deduplicate before return
        all_povs: list[PoV] = []
        for pov in fuzzing_povs + llm_povs:
            if not self._deduplicator.is_duplicate(pov):
                self._deduplicator.register(pov)
                all_povs.append(pov)

        logger.info(
            "PoV generation complete: fuzzing=%d llm=%d unique=%d",
            len(fuzzing_povs), len(llm_povs), len(all_povs),
        )
        return all_povs

    async def _bootstrap_seeds(self, challenge: Any) -> list[bytes]:
        """§6.1 — Seed corpus bootstrapping from pre-competition corpus + LLM generation."""
        seeds: list[bytes] = []
        # TODO: Load pre-competition corpus from OSS-Fuzz/ClusterFuzz/GitHub
        # TODO: Run seed_agent to generate additional seeds from harness analysis
        return seeds

    async def _run_fuzzing_pipeline(
        self,
        challenge: Any,
        seed_corpus: list[bytes],
        enable_fuzz_to_llm: bool,
    ) -> list[PoV]:
        """§6.1 — Fuzzing Pipeline execution."""
        return await self._fuzzer.run(
            repo_path=challenge.repo_path,
            harness_paths=challenge.harness_paths,
            seed_corpus=seed_corpus,
            time_limit_seconds=challenge.time_limit_seconds,
        )

    async def _run_llm_pipeline(
        self, challenge: Any, enable_llm_to_fuzz: bool
    ) -> list[PoV]:
        """§6.1 — LLM-Based PoV Generation Pipeline execution."""
        # Step 1: Identify bug candidates
        candidates = await self._candidate_id.identify(challenge.repo_path)
        logger.info(
            "Bug candidates identified: %d for challenge %s",
            len(candidates), challenge.challenge_id,
        )

        # Step 2: Generate PoVs for each candidate
        all_povs: list[PoV] = []
        for candidate in candidates:
            cwe_guidance = self._get_cwe_guidance(candidate.cwe_id)
            povs = await self._llm_agent.generate(
                candidate=candidate,
                repo_path=challenge.repo_path,
                cwe_guidance=cwe_guidance,
            )
            all_povs.extend(povs)

            # §6.1 — LLM PoV Gen→Fuzz cooperation
            if enable_llm_to_fuzz:
                for pov in povs:
                    await self._fuzzer.receive_from_llm(pov)

        return all_povs

    def _get_cwe_guidance(self, cwe_id: Optional[str]) -> Optional[str]:
        """§6.1 — "Four teams inject CWE-specific guidance to steer exploit construction."

        TODO: Populate with CWE exploitation knowledge base.
        CWE-119 (buffer overflow), CWE-416 (use-after-free), CWE-190 (integer overflow), etc.
        """
        if not cwe_id:
            return None
        # TODO: Load from a CWE knowledge base
        return f"[CWE-{cwe_id} exploitation guidance — populate from knowledge base]"
