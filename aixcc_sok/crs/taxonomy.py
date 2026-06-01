"""
AIxCC SoK — CRS Technique Taxonomy
Paper: https://arxiv.org/abs/2602.07666

§5, §6, Tables 2–6:
    Machine-readable taxonomy of the seven finalist CRS designs.
    Captures technique presence (Tables 3, 4, 5, 6) and design philosophy (Table 2).

Usage:
    from crs.taxonomy import CRSTaxonomy, FINALIST_TEAMS
    team = FINALIST_TEAMS["AT"]
    print(team.pov.fuzzing.pre_competition_corpus)  # True
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Table 2 — §5: Team metadata
# ---------------------------------------------------------------------------

@dataclass
class TeamMetadata:
    """§5, Table 2 — Background information for each finalist CRS team."""

    # §5 Table 2 — Team identifier (abbreviated)
    id: str
    # §5 Table 2 — Full team name
    team_name: str
    # §5 Table 2 — CRS system name
    crs_name: str
    # §5 Table 2 — Background (Mixed = academia+industry, Academic, Industry)
    background: str
    # §5 Table 2 — Primary languages
    languages: list[str]
    # §5 Table 2 — LLM orchestration library
    llm_lib: str
    # §5 Table 2 — Final competition rank (1 = highest score)
    final_rank: int
    # §5 — One-sentence design philosophy
    philosophy: str


# ---------------------------------------------------------------------------
# Table 3 — §6.1: PoV Generation Techniques
# ---------------------------------------------------------------------------

@dataclass
class FuzzingPipelineTechniques:
    """§6.1, Table 3 (rows: Fuzzing Pipeline) — LLM-non-LLM fuzzing enhancements."""

    # §6.1 — "Five teams reused pre-collected corpora to bootstrap fuzzer coverage"
    pre_competition_corpus: bool = False
    # §6.1 — "Six teams use LLMs to generate seeds: early-stage bootstrap and troubleshooting"
    seed_gen_agent: bool = False
    # §6.1 — "Bootstrap" (seed gen at competition start)
    seed_bootstrap: bool = False
    # §6.1 — "Solve coverage blockers" via LLM-generated inputs
    solve_cov_blocker: bool = False
    # §6.1 — "AT, TI, SP explored generating input mutators/generators and explicit grammars"
    mutator_or_generator: bool = False
    # §6.1 — "AT, TB, SP" grammar-aware fuzzing (testlang/libFDP/Nautilus grammars)
    grammar_aware: bool = False
    # §6.1 — "AT, SP, 42" refined internal fuzzer components (feedback, oracle, dict, scheduler)
    engine_refinement: bool = False
    # §6.1 — "SP added semantic feedback by having LLMs generate IJON-style annotations"
    semantic_feedback: bool = False
    # §6.1 — "AT and SP improved the Java sanitizers to strengthen fuzzer guidance"
    improved_sanitizer: bool = False
    # §6.1 — "four teams produced fuzzing dictionaries" (AT, SP, 42, LC)
    dict_gen: bool = False
    # §6.1 — "AT and 42 customized scheduling with directed fuzzing"
    directed_fuzzing: bool = False
    # §6.1 — "AT explored hybrid fuzzers: SymCC-based for C and from-scratch for Java"
    concolic_fuzzing: bool = False
    # §6.1 — "all teams run multiple fuzzer instances in parallel"
    parallel_fuzzing: bool = True
    # §6.1 — "synchronize corpora across instances (except FB)"
    corpus_sync: bool = False
    # §6.1 — "AT, SP, 42, LC added custom C fuzzers (AFL++, libAFL, or custom)"
    added_c_fuzzers: bool = False
    # §6.1 — "AT also covering JVM via libAFL"
    added_jvm_fuzzers: bool = False


@dataclass
class LLMPoVPipelineTechniques:
    """§6.1, Table 3 (rows: LLM-Based PoV Generation Pipeline)."""

    # §6.1 — "Five teams build agent systems combining LLMs, static analysis, and sink lists"
    bug_candidate_identification: bool = False
    # §6.1 — "Two distinctive filtering: TI uses LLM logprobs; SP/LC use weighted votes"
    candidate_filter: bool = False
    # §6.1 — "LLM logprobs as token-efficient confidence signal" (TI)
    logprob_filtering: bool = False
    # §6.1 — "aggregate weighted votes across multiple tools and LLMs" (SP, LC)
    weighted_vote_filter: bool = False
    # §6.1 — "Five teams construct PoV-generation agents over static and dynamic analysis tools"
    pov_gen_agent: bool = False
    # §6.1 — "Four teams inject CWE-specific guidance" (AT, TB, FB, SP)
    cwe_guidance: bool = False
    # §6.1 — "Three further decompose: reach agent drives to sink, exploit agent crafts trigger" (AT, TI, SP)
    reach_then_exploit: bool = False
    # §6.1 — "LC performs only bug candidate identification, feeds to no-PoV patch generation"
    non_pov_gen_usage: bool = False


@dataclass
class PoVCooperationTechniques:
    """§6.1, Table 3 (rows: Pipeline Cooperation)."""

    # §6.1 — "five teams: LLM PoV Gen→Fuzz — successful/failed/intermediate results shared with fuzzers"
    llm_to_fuzz: bool = False
    # §6.1 — "three teams: Fuzz→LLM PoV Gen — coverage info + reached-but-unexploited inputs" (AT, TI, SP)
    fuzz_to_llm: bool = False


@dataclass
class PoVSubmissionTechniques:
    """§6.1, Table 3 (rows: PoV Submission)."""

    # §6.1 — "All teams adopt straightforward strategies: submit unique PoVs as soon as possible"
    asap_submission: bool = True
    # §6.1 — "all teams implement deduplication using crash stack traces, input hashing, sanitizer signatures"
    deduplication: bool = True
    # §6.1 — "TI and FB further use LLMs to group semantically equivalent PoVs"
    llm_semantic_dedup: bool = False


@dataclass
class PoVGenerationTechniques:
    """§6.1, Table 3 — Complete PoV generation technique profile for one team."""

    fuzzing: FuzzingPipelineTechniques = field(default_factory=FuzzingPipelineTechniques)
    llm_pipeline: LLMPoVPipelineTechniques = field(default_factory=LLMPoVPipelineTechniques)
    cooperation: PoVCooperationTechniques = field(default_factory=PoVCooperationTechniques)
    submission: PoVSubmissionTechniques = field(default_factory=PoVSubmissionTechniques)


# ---------------------------------------------------------------------------
# Table 4 — §6.2: Patch Generation Techniques
# ---------------------------------------------------------------------------

@dataclass
class AgentArchTechniques:
    """§6.2, Table 4 (rows: Agent Arch.) — Patcher agent architecture pattern."""

    # §6.2 — "AT ensembles eight patcher agents spanning diverse designs"
    multi_arch: bool = False
    # §6.2 — "TB organizes four agents into pipeline; TI uses hierarchical design"
    multi_agent: bool = False
    # §6.2 — "FB: 23 strategies; 42: 16 config combos; LC: DSPy model escalation"
    single_agent: bool = False


@dataclass
class RCATechniques:
    """§6.2, Table 4 (rows: RCA)."""

    # §6.2 — "AT, TB, TI, SP implement standalone RCA components"
    standalone_rca: bool = False
    # §6.2 — "TB, TI, SP leverage information from multiple PoVs"
    multi_pov_rca: bool = False
    # §6.2 — "SP incorporates a non-LLM RCA combining SAST, stack traces, fuzzing invariants with weighted voting"
    non_llm_rca: bool = False


@dataclass
class GenerationTechniques:
    """§6.2, Table 4 (rows: Generation)."""

    # §6.2 — "crash/sanitizer output ... used by all teams" (in contextualization)
    # Note: base flag; all teams True
    contextualization_crash: bool = True
    # §6.2 — "agentic code search over project code ... used by all teams"
    code_search: bool = True
    # §6.2 — "pre-built code indexers for symbol lookups (5 teams)"
    code_indexer: bool = False
    # §6.2 — "SAST reports static analysis outcomes (4 teams)"
    sast: bool = False
    # §6.2 — "CWE-specific vulnerability domain knowledge (2 teams)"
    cwe_guidance: bool = False
    # §6.2 — "LLM fine-tuning (Llama) for context retrieval (1 team)" — TB only
    fine_tuned_llm: bool = False
    # §6.2 — "agentic code search" (all teams; listed separately for completeness)
    agentic_code_search: bool = True
    # §6.2 — "runtime probes (debugger, coverage instrumentation) (4 teams)"
    dynamic_info: bool = False
    # §6.2 — "PoV bytes that triggered the bug (3 teams)"
    pov_bytes: bool = False
    # §6.2 — "five CRSs adopted LLM reflection"
    llm_reflection: bool = False
    # §6.2 — "three CRSs attempt patch generation for vulnerability candidate without PoV"
    no_pov_patch_gen: bool = False


@dataclass
class ValidationTechniques:
    """§6.2, Table 4 (rows: Validation)."""

    # §6.2 — "build verification" (all teams)
    build_check: bool = True
    # §6.2 — "PoV Test (Gen): single/multiple/all PoVs during generation"
    # [PARTIALLY_SPECIFIED] Specific count varies per team; 1=single, N=multiple, *=all
    pov_test_gen: str = "1"  # "1", "N", or "*"
    # §6.2 — "project test suites (42 skips project tests)"
    project_tests: bool = True
    # §6.2 — "PoV Test (Submit): revalidate against broader PoV set before submission"
    pov_test_submit: str = "*"  # "1", "N", or "*"
    # §6.2 — "three CRSs incorporate LLM-based evaluation"
    llm_as_judge: bool = False
    # §6.2 — "FB and SP adopt short-term fuzzing on patched projects for incomplete patch detection"
    post_patch_fuzz: bool = False
    # §6.2 — "AT and SP employ build caching (ccache for C/C++, Maven caching for Java)"
    rebuild_optimization: bool = False


@dataclass
class DedupSubmitTechniques:
    """§6.2, Table 4 (rows: Dedup & Sub.)."""

    # §6.2 — "four CRSs compute a minimal patch set that covers all known PoVs" (AT, TB, SP, 42)
    minimal_patch_set: bool = False
    # §6.2 — "three CRSs with No-PoV capability delay submission" (TI, FB, LC)
    no_pov_delayed_sub: Optional[bool] = None  # None = N/A (no No-PoV capability)


@dataclass
class PatchGenerationTechniques:
    """§6.2, Table 4 — Complete patch generation technique profile for one team."""

    agent_arch: AgentArchTechniques = field(default_factory=AgentArchTechniques)
    rca: RCATechniques = field(default_factory=RCATechniques)
    generation: GenerationTechniques = field(default_factory=GenerationTechniques)
    validation: ValidationTechniques = field(default_factory=ValidationTechniques)
    dedup_submit: DedupSubmitTechniques = field(default_factory=DedupSubmitTechniques)


# ---------------------------------------------------------------------------
# Table 5 — §6.3: SARIF Validation Strategies
# ---------------------------------------------------------------------------

@dataclass
class SARIFValidationTechniques:
    """§6.3, Table 5 — SARIF submission strategy for one team."""

    # §6.3 — three strategy categories
    # "PoV-centric: match SARIF locations against crash info from exploited vulnerabilities"
    pov_centric: bool = False
    # "LLM-judge-centric: agentic prompting to directly assess correctness"
    llm_judge_centric: bool = False
    # "Bug-cand-centric: matching SARIF reports against bug candidate database"
    bug_cand_centric: bool = False
    # §6.3 — "FB additionally uses fallback LLM judgement, only submits Correct from it"
    llm_fallback_correct_only: bool = False
    # §6.3 — whether team submits Incorrect verdicts (risky; incurs penalties)
    submits_incorrect: bool = False


# ---------------------------------------------------------------------------
# Table 6 — §6.4: Bundling Pairing Strategies
# ---------------------------------------------------------------------------

@dataclass
class BundlingTechniques:
    """§6.4, Table 6 — Bundle pairing strategies for one team."""

    # §6.4 — "All teams naturally derive PoV-Patch from PoV-based patch generation"
    pov_patch_from_gen: bool = True
    # §6.4 — "retroactively link PoVs to No-PoV patches once discovered" (TI only)
    pov_patch_retroactive: bool = False
    # §6.4 — "reuse SARIF validation results for PoV-SARIF"
    pov_sarif_from_validation: bool = False
    # §6.4 — "use SARIF reports to generate PoVs" (SARIF-guided PoV) (FB only)
    pov_sarif_guided_pov: bool = False
    # §6.4 — "bug candidate DB links patch to SARIF" (TI, FB only — no-PoV capability)
    patch_sarif_from_bug_db: bool = False
    # §6.4 — "SARIF-guided patch generation" (FB only)
    patch_sarif_guided: bool = False


# ---------------------------------------------------------------------------
# Full per-team profile
# ---------------------------------------------------------------------------

@dataclass
class CRSProfile:
    """Complete technique profile for one finalist CRS team."""

    metadata: TeamMetadata
    pov: PoVGenerationTechniques
    patch: PatchGenerationTechniques
    sarif: SARIFValidationTechniques
    bundling: BundlingTechniques


# ---------------------------------------------------------------------------
# §5, §6, Tables 2–6: FINALIST_TEAMS — canonical data from paper
# ---------------------------------------------------------------------------

FINALIST_TEAMS: dict[str, CRSProfile] = {

    "AT": CRSProfile(
        metadata=TeamMetadata(
            id="AT", team_name="Team Atlanta", crs_name="ATLANTIS",
            background="Mixed", languages=["Python", "Rust"],
            llm_lib="LangGraph+LiteLLM",
            final_rank=1,
            # §5 — "any technique demonstrating unique contribution is worth incorporating"
            philosophy="Ensemble-First Design: any technique with unique contribution included; "
                       "8 patching agents with diverse repair strategies.",
        ),
        pov=PoVGenerationTechniques(
            fuzzing=FuzzingPipelineTechniques(
                pre_competition_corpus=True, seed_gen_agent=True,
                seed_bootstrap=True, solve_cov_blocker=True,
                mutator_or_generator=True, grammar_aware=True,
                engine_refinement=True, improved_sanitizer=True,
                dict_gen=True, directed_fuzzing=True,
                concolic_fuzzing=True, parallel_fuzzing=True,
                corpus_sync=True, added_c_fuzzers=True, added_jvm_fuzzers=True,
            ),
            llm_pipeline=LLMPoVPipelineTechniques(
                bug_candidate_identification=True, candidate_filter=True,
                pov_gen_agent=True, cwe_guidance=True, reach_then_exploit=True,
            ),
            cooperation=PoVCooperationTechniques(llm_to_fuzz=True, fuzz_to_llm=True),
            submission=PoVSubmissionTechniques(asap_submission=True, deduplication=True),
        ),
        patch=PatchGenerationTechniques(
            agent_arch=AgentArchTechniques(multi_arch=True),
            rca=RCATechniques(standalone_rca=True),
            generation=GenerationTechniques(
                code_indexer=True, sast=True, dynamic_info=True,
                pov_bytes=True, llm_reflection=True,
            ),
            validation=ValidationTechniques(
                pov_test_gen="1", pov_test_submit="*",
                rebuild_optimization=True,
            ),
            dedup_submit=DedupSubmitTechniques(minimal_patch_set=True, no_pov_delayed_sub=None),
        ),
        sarif=SARIFValidationTechniques(pov_centric=True),
        bundling=BundlingTechniques(
            pov_patch_from_gen=True, pov_sarif_from_validation=True,
        ),
    ),

    "TB": CRSProfile(
        metadata=TeamMetadata(
            id="TB", team_name="Trail of Bits", crs_name="BUTTERCUP",
            background="Industry", languages=["Python"],
            llm_lib="LangGraph", final_rank=2,
            # §5 — "deterministic workflows; LLMs only where traditional tools fall short"
            philosophy="Expertise-Driven Decomposition: deterministic workflows, mid-tier LLMs, "
                       "4-agent pipeline (RCA→fix-strategy→patch→reflection).",
        ),
        pov=PoVGenerationTechniques(
            fuzzing=FuzzingPipelineTechniques(
                pre_competition_corpus=True, seed_gen_agent=True,
                seed_bootstrap=True, solve_cov_blocker=True,
                parallel_fuzzing=True, corpus_sync=True,
            ),
            llm_pipeline=LLMPoVPipelineTechniques(
                pov_gen_agent=True, cwe_guidance=True,
            ),
            cooperation=PoVCooperationTechniques(llm_to_fuzz=True),
            submission=PoVSubmissionTechniques(asap_submission=True, deduplication=True),
        ),
        patch=PatchGenerationTechniques(
            agent_arch=AgentArchTechniques(multi_agent=True),
            rca=RCATechniques(standalone_rca=True, multi_pov_rca=True),
            generation=GenerationTechniques(
                code_indexer=True, sast=True, dynamic_info=True,
                fine_tuned_llm=True, llm_reflection=True,
            ),
            validation=ValidationTechniques(
                pov_test_gen="N", pov_test_submit="N", project_tests=True,
            ),
            dedup_submit=DedupSubmitTechniques(minimal_patch_set=True),
        ),
        sarif=SARIFValidationTechniques(pov_centric=True),
        bundling=BundlingTechniques(
            pov_patch_from_gen=True, pov_sarif_from_validation=True,
        ),
    ),

    "TI": CRSProfile(
        metadata=TeamMetadata(
            id="TI", team_name="Theori", crs_name="ROBODUCK",
            background="Industry", languages=["Python", "Rust"],
            llm_lib="Self-built+LiteLLM", final_rank=3,
            # §5 — "agentic-first philosophy; entire system revolves around bug candidates"
            philosophy="Agentic Design around Bug Candidates: custom agent library, "
                       "hierarchical ReAct outer loop with SourceQuestionsAgent inner tool.",
        ),
        pov=PoVGenerationTechniques(
            fuzzing=FuzzingPipelineTechniques(
                pre_competition_corpus=True, seed_gen_agent=True,
                seed_bootstrap=True, solve_cov_blocker=True,
                mutator_or_generator=True, parallel_fuzzing=True,
                corpus_sync=True, added_c_fuzzers=True,
            ),
            llm_pipeline=LLMPoVPipelineTechniques(
                bug_candidate_identification=True, candidate_filter=True,
                logprob_filtering=True,
                pov_gen_agent=True, reach_then_exploit=True,
            ),
            cooperation=PoVCooperationTechniques(llm_to_fuzz=True, fuzz_to_llm=True),
            submission=PoVSubmissionTechniques(
                asap_submission=True, deduplication=True, llm_semantic_dedup=True,
            ),
        ),
        patch=PatchGenerationTechniques(
            agent_arch=AgentArchTechniques(multi_agent=True),
            rca=RCATechniques(standalone_rca=True, multi_pov_rca=True),
            generation=GenerationTechniques(
                code_indexer=True, dynamic_info=True,
                pov_bytes=True, llm_reflection=True, no_pov_patch_gen=True,
            ),
            validation=ValidationTechniques(
                pov_test_gen="*", pov_test_submit="*", project_tests=True,
            ),
            dedup_submit=DedupSubmitTechniques(minimal_patch_set=False, no_pov_delayed_sub=True),
        ),
        sarif=SARIFValidationTechniques(bug_cand_centric=True, submits_incorrect=True),
        bundling=BundlingTechniques(
            pov_patch_from_gen=True, pov_patch_retroactive=True,
            pov_sarif_from_validation=True,
            patch_sarif_from_bug_db=True,
        ),
    ),

    "FB": CRSProfile(
        metadata=TeamMetadata(
            id="FB", team_name="Fuzzing Brain", crs_name="FUZZINGBRAIN",
            background="Academic", languages=["Python", "Go"],
            llm_lib="None (direct API)", final_rank=4,
            # §5 — "90% vibecoded; 23 independent strategies as standalone Python scripts"
            philosophy="Simple Architecture, Diverse LLM Strategies: minimal infra, "
                       "23 standalone scripts varying in scope/depth/language-handling.",
        ),
        pov=PoVGenerationTechniques(
            fuzzing=FuzzingPipelineTechniques(
                pre_competition_corpus=True, seed_gen_agent=True,
                seed_bootstrap=True, parallel_fuzzing=True,
                added_c_fuzzers=True,
            ),
            llm_pipeline=LLMPoVPipelineTechniques(
                bug_candidate_identification=True, candidate_filter=True,
                pov_gen_agent=True, cwe_guidance=True,
            ),
            cooperation=PoVCooperationTechniques(llm_to_fuzz=True),
            submission=PoVSubmissionTechniques(
                asap_submission=True, deduplication=True, llm_semantic_dedup=True,
            ),
        ),
        patch=PatchGenerationTechniques(
            agent_arch=AgentArchTechniques(single_agent=True),
            rca=RCATechniques(),
            generation=GenerationTechniques(
                code_indexer=True, llm_reflection=True, no_pov_patch_gen=True,
            ),
            validation=ValidationTechniques(
                pov_test_gen="1", pov_test_submit="N",
                llm_as_judge=True, post_patch_fuzz=True,
            ),
            dedup_submit=DedupSubmitTechniques(minimal_patch_set=False, no_pov_delayed_sub=True),
        ),
        sarif=SARIFValidationTechniques(
            pov_centric=True, llm_fallback_correct_only=True,
        ),
        bundling=BundlingTechniques(
            pov_patch_from_gen=True,
            pov_sarif_from_validation=True,
            pov_sarif_guided_pov=True,
            patch_sarif_from_bug_db=True,
            patch_sarif_guided=True,
        ),
    ),

    "SP": CRSProfile(
        metadata=TeamMetadata(
            id="SP", team_name="Shellphish", crs_name="ARTIPHISHELL",
            background="Academic", languages=["Python"],
            llm_lib="Self-built+LiteLLM", final_rank=5,
            # §5 — "53 components; custom orchestration platform for inter-component communication"
            philosophy="Comprehensive Technical Coverage: diverse techniques across all four "
                       "capabilities, custom orchestration platform for 53 components.",
        ),
        pov=PoVGenerationTechniques(
            fuzzing=FuzzingPipelineTechniques(
                pre_competition_corpus=True, seed_gen_agent=True,
                seed_bootstrap=True, solve_cov_blocker=True,
                mutator_or_generator=True, grammar_aware=True,
                engine_refinement=True, semantic_feedback=True,
                improved_sanitizer=True, dict_gen=True,
                parallel_fuzzing=True, corpus_sync=True,
                added_c_fuzzers=True,
            ),
            llm_pipeline=LLMPoVPipelineTechniques(
                bug_candidate_identification=True, candidate_filter=True,
                weighted_vote_filter=True,
                pov_gen_agent=True, cwe_guidance=True, reach_then_exploit=True,
            ),
            cooperation=PoVCooperationTechniques(llm_to_fuzz=True, fuzz_to_llm=True),
            submission=PoVSubmissionTechniques(asap_submission=True, deduplication=True),
        ),
        patch=PatchGenerationTechniques(
            agent_arch=AgentArchTechniques(multi_arch=True),
            rca=RCATechniques(standalone_rca=True, multi_pov_rca=True, non_llm_rca=True),
            generation=GenerationTechniques(
                code_indexer=True, sast=True, dynamic_info=True,
                pov_bytes=True, llm_reflection=True,
            ),
            validation=ValidationTechniques(
                pov_test_gen="N", pov_test_submit="*",
                llm_as_judge=True, post_patch_fuzz=True, rebuild_optimization=True,
            ),
            dedup_submit=DedupSubmitTechniques(minimal_patch_set=True, no_pov_delayed_sub=None),
        ),
        sarif=SARIFValidationTechniques(
            llm_judge_centric=True, submits_incorrect=True,
        ),
        bundling=BundlingTechniques(
            pov_patch_from_gen=True, pov_sarif_from_validation=True,
        ),
    ),

    "42": CRSProfile(
        metadata=TeamMetadata(
            id="42", team_name="42-b3yond-6ug", crs_name="BUGBUSTER",
            background="Academic", languages=["Python", "Go"],
            llm_lib="LangChain+LiteLLM", final_rank=6,
            # §5 — "pragmatic, simple and stable technology choices; LLMs limited to auxiliary roles"
            philosophy="Pragmatic Technology Choices: simple/stable, traditional fuzzing and "
                       "program analysis centric, 16-combo single-agent diversity.",
        ),
        pov=PoVGenerationTechniques(
            fuzzing=FuzzingPipelineTechniques(
                seed_gen_agent=True, seed_bootstrap=True,
                engine_refinement=True, dict_gen=True,
                directed_fuzzing=True, parallel_fuzzing=True,
                corpus_sync=True, added_c_fuzzers=True,
            ),
            llm_pipeline=LLMPoVPipelineTechniques(
                bug_candidate_identification=True, candidate_filter=True,
                # §5 — "LLMs limited to auxiliary roles like seed generation" — no dedicated PoV gen agent
                # §6.1 — "five teams construct PoV-generation agents"; 42 is not listed
                pov_gen_agent=False,
            ),
            cooperation=PoVCooperationTechniques(llm_to_fuzz=True),
            submission=PoVSubmissionTechniques(asap_submission=True, deduplication=True),
        ),
        patch=PatchGenerationTechniques(
            agent_arch=AgentArchTechniques(single_agent=True),
            rca=RCATechniques(),
            generation=GenerationTechniques(
                code_indexer=True, sast=True, dynamic_info=True, llm_reflection=True,
            ),
            validation=ValidationTechniques(
                pov_test_gen="1", pov_test_submit="*",
                project_tests=False,
            ),
            dedup_submit=DedupSubmitTechniques(minimal_patch_set=True, no_pov_delayed_sub=None),
        ),
        sarif=SARIFValidationTechniques(
            llm_judge_centric=True, submits_incorrect=True,
        ),
        bundling=BundlingTechniques(pov_patch_from_gen=True),
    ),

    "LC": CRSProfile(
        metadata=TeamMetadata(
            id="LC", team_name="Lacrosse", crs_name="LACROSSE",
            background="Industry", languages=["Python", "Lisp"],
            llm_lib="DSPy+LiteLLM", final_rank=7,
            # §5 — "Lisp-based task distributor; DSPy manages diverse LLMs with patch failure feedback"
            philosophy="DSPy-Based Multi-LLM Workflow: Lisp task distributor, "
                       "DSPy parallel/fallback LLM management, patch failures refine vulnerability analysis.",
        ),
        pov=PoVGenerationTechniques(
            fuzzing=FuzzingPipelineTechniques(
                seed_gen_agent=True, dict_gen=True,
                parallel_fuzzing=True, corpus_sync=True,
                added_c_fuzzers=True,
            ),
            llm_pipeline=LLMPoVPipelineTechniques(
                bug_candidate_identification=True, candidate_filter=True,
                weighted_vote_filter=True, non_pov_gen_usage=True,
            ),
            cooperation=PoVCooperationTechniques(llm_to_fuzz=True),
            submission=PoVSubmissionTechniques(asap_submission=True, deduplication=True),
        ),
        patch=PatchGenerationTechniques(
            agent_arch=AgentArchTechniques(single_agent=True),
            rca=RCATechniques(),
            generation=GenerationTechniques(no_pov_patch_gen=True),
            validation=ValidationTechniques(
                pov_test_gen="1", pov_test_submit="1",
            ),
            dedup_submit=DedupSubmitTechniques(minimal_patch_set=False, no_pov_delayed_sub=True),
        ),
        sarif=SARIFValidationTechniques(
            llm_judge_centric=True, submits_incorrect=True,
        ),
        bundling=BundlingTechniques(pov_patch_from_gen=True),
    ),
}


def technique_adoption_rate(technique_path: str) -> float:
    """Return fraction of teams (0.0–1.0) that adopted a given technique.

    technique_path: dot-separated path into CRSProfile, e.g. "pov.fuzzing.parallel_fuzzing"

    Example:
        rate = technique_adoption_rate("pov.fuzzing.directed_fuzzing")  # 2/7 = 0.286
    """
    parts = technique_path.split(".")
    count = 0
    for profile in FINALIST_TEAMS.values():
        obj = profile
        for part in parts:
            obj = getattr(obj, part, None)
            if obj is None:
                break
        if obj is True:
            count += 1
    return count / len(FINALIST_TEAMS)
