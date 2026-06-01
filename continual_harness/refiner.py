"""
Continual Harness — Refiner
§3.2: Four-pass harness refinement from trajectory window.

The Refiner reads τ_{t-F:t} (the last F steps), identifies failure signatures,
then runs four passes emitting Δ=(Δp, ΔG, ΔK, ΔM) via an LLM call per pass.

§3.1: "Agent and Refiner roles share the same model M"
§3.2: Failure signatures = navigation loops, tool-call failures, stalled objectives,
      missed exploration opportunities.
"""
from __future__ import annotations
import json
import re
from typing import Any

from .harness_state import HarnessEdit, HarnessState, MemoryEntry
from .muse_skill import MUSESkillManager

# Failure signature taxonomy from §3.2
_FAILURE_PATTERNS = {
    "navigation_loop": re.compile(
        r"(same location|stuck at|loop detected|revisiting|no progress)", re.I
    ),
    "tool_call_failure": re.compile(
        r"(exception|error|traceback|failed to call|tool call failed)", re.I
    ),
    "stalled_objective": re.compile(
        r"(objective unchanged|no milestone|stalled|blocked on)", re.I
    ),
    "missed_exploration": re.compile(
        r"(unexplored|skipped|forgot to|missed opportunity)", re.I
    ),
}


def detect_failure_signatures(trajectory_text: str) -> dict[str, bool]:
    """§3.2: scan trajectory window for the four failure signature categories."""
    return {
        sig: bool(pat.search(trajectory_text))
        for sig, pat in _FAILURE_PATTERNS.items()
    }


class Refiner:
    """
    §3.1–3.2: LLM-backed Refiner that reads a trajectory window and emits HarnessEdit.

    [UNSPECIFIED] Whether Refiner uses one LLM call per pass (4 calls) or one combined call.
    Using: one call per pass (matches §3.2 "runs four passes") for clarity and
    easier debugging of each component's edits.
    [UNSPECIFIED] Prompt format / few-shot examples for the Refiner.
    Using: structured JSON-output prompts — the meta-tool API in §2.2 implies
    structured machine-readable edits.
    """

    def __init__(self, llm_callable: Any, muse: MUSESkillManager | None = None):
        """
        llm_callable: any callable(prompt: str) -> str.
        muse: optional MUSESkillManager — if provided, Pass (iii) uses the full
              MUSE lifecycle (create→eval→refine→register) instead of raw strings.
        """
        self._llm = llm_callable
        self._muse = muse

    def refine(
        self,
        state: HarnessState,
        trajectory: list[dict],
        failures: dict[str, bool] | None = None,
    ) -> HarnessEdit:
        """
        §3.2: Four-pass refinement over trajectory window.
        Returns HarnessEdit with all four Δ components populated.
        """
        traj_text = _format_trajectory(trajectory)
        if failures is None:
            failures = detect_failure_signatures(traj_text)

        active_failures = [k for k, v in failures.items() if v]
        failure_summary = (
            ", ".join(active_failures) if active_failures else "none detected"
        )

        delta = HarnessEdit()

        # Pass (i): rewrite system prompt p
        # §3.2: "rewrites p conditioned on identified failures and trajectory window"
        delta.new_p = self._pass_prompt(state.p, traj_text, failure_summary)

        # Pass (ii): CRUD sub-agents G
        # §3.2: "creates entries for repeated multi-step patterns, edits existing entries
        # to address failures, deletes entries not invoked productively"
        g_edit = self._pass_subagents(state.G, traj_text, failure_summary)
        delta.G_create = g_edit.get("create", {})
        delta.G_update = g_edit.get("update", {})
        delta.G_delete = g_edit.get("delete", [])

        # Pass (iii): CRUD skills K
        # §3.2: "codifies skills from successful sequences and repairs executable code
        # that raised exceptions"
        # If MUSESkillManager is wired in, use full lifecycle (2605.27366 §3.2):
        #   spec → create → eval → refine → register (or repair existing on failure)
        if self._muse is not None:
            k_edit = self._pass_skills_muse(state.K, traj_text, failure_summary)
        else:
            k_edit = self._pass_skills(state.K, traj_text, failure_summary)
        delta.K_create = k_edit.get("create", {})
        delta.K_update = k_edit.get("update", {})
        delta.K_delete = k_edit.get("delete", [])

        # Pass (iv): CRUD memory M
        # §3.2: "adds memory entries to fill gaps, updates stale entries, demotes
        # importance for areas the agent has moved past"
        m_edit = self._pass_memory(state.M, traj_text, failure_summary)
        delta.M_add = [MemoryEntry(**e) for e in m_edit.get("add", [])]
        delta.M_updates = m_edit.get("updates", [])
        delta.M_demotions = m_edit.get("demotions", [])

        return delta

    # ── MUSE skill pass (2605.27366) ─────────────────────────────────────────

    def _pass_skills_muse(self, current_K: dict, traj: str, failures: str) -> dict:
        """
        Pass (iii) with MUSE lifecycle (arxiv 2605.27366 §3.2):
        LLM identifies needed skills from trajectory, then MUSESkillManager
        runs create→eval→refine→register for each new spec, and repairs
        any skills that raised exceptions during the trajectory window.
        """
        # Identify needed skills and broken ones from trajectory
        prompt = f"""Analyze this agent trajectory and identify:
1. New skills to create (repeated multi-step patterns worth encapsulating)
2. Existing skills that raised exceptions and need repair

FAILURE SIGNATURES: {failures}
CURRENT SKILLS: {list(current_K.keys())}
TRAJECTORY: {traj[:2000]}

Output JSON:
{{"new_specs": ["high-level spec for skill 1", "..."], "broken": ["skill_name_that_failed"]}}"""
        raw = self._llm(prompt)
        data = _parse_json_response(raw, {"new_specs": [], "broken": []})

        created: dict[str, str] = {}
        for spec in data.get("new_specs", [])[:3]:  # cap at 3 new skills per cycle
            name, ok = self._muse.create_and_register(spec)
            if ok:
                pkg = self._muse.bank.get(name)
                created[name] = pkg.skill_md if pkg else spec

        for broken_name in data.get("broken", []):
            self._muse.repair_skill(broken_name, traj[-500:])

        return {"create": created, "update": {}, "delete": []}

    # ── LLM pass helpers ──────────────────────────────────────────────────────

    def _pass_prompt(self, current_p: str, traj: str, failures: str) -> str:
        prompt = f"""You are the Refiner in a Continual Harness (arxiv 2605.09998).
Your task: rewrite the agent's system prompt to address observed failures.

FAILURE SIGNATURES DETECTED: {failures}

CURRENT SYSTEM PROMPT:
{current_p}

RECENT TRAJECTORY (last F steps):
{traj}

Output ONLY the new system prompt text. No explanation. No JSON wrapper."""
        result = self._llm(prompt)
        return result.strip() if result.strip() else current_p

    def _pass_subagents(
        self, current_G: dict[str, str], traj: str, failures: str
    ) -> dict:
        prompt = f"""You are the Refiner — sub-agent pass (§3.2 of arxiv 2605.09998).

FAILURE SIGNATURES: {failures}
CURRENT SUB-AGENTS: {json.dumps(current_G, indent=2)}
TRAJECTORY: {traj}

Create entries for repeated multi-step patterns.
Edit existing entries to address detected failures.
Delete entries not invoked productively.

Output JSON with this exact schema:
{{
  "create": {{"agent_name": "agent spec string"}},
  "update": {{"agent_name": "updated spec string"}},
  "delete": ["agent_name_to_remove"]
}}"""
        return _parse_json_response(self._llm(prompt), {"create": {}, "update": {}, "delete": []})

    def _pass_skills(
        self, current_K: dict[str, str], traj: str, failures: str
    ) -> dict:
        prompt = f"""You are the Refiner — skills pass (§3.2 of arxiv 2605.09998).

FAILURE SIGNATURES: {failures}
CURRENT SKILLS: {json.dumps(current_K, indent=2)}
TRAJECTORY: {traj}

Codify reusable routines from successful sequences.
Repair any executable code that raised exceptions.

Output JSON:
{{
  "create": {{"skill_name": "skill code or spec"}},
  "update": {{"skill_name": "repaired code or spec"}},
  "delete": ["skill_name_to_remove"]
}}"""
        return _parse_json_response(self._llm(prompt), {"create": {}, "update": {}, "delete": []})

    def _pass_memory(self, current_M: list[MemoryEntry], traj: str, failures: str) -> dict:
        mem_repr = [{"index": i, **e.to_dict()} for i, e in enumerate(current_M)]
        prompt = f"""You are the Refiner — memory pass (§3.2 of arxiv 2605.09998).

FAILURE SIGNATURES: {failures}
CURRENT MEMORY (with indices): {json.dumps(mem_repr, indent=2)}
TRAJECTORY: {traj}

Add entries to fill knowledge gaps.
Update stale entries with corrected content.
Demote importance (toward 0.0) for areas the agent has moved past.

Output JSON:
{{
  "add": [{{"content": "...", "importance": 1.0, "tags": []}}],
  "updates": [{{"index": 0, "content": "...", "importance": 0.8}}],
  "demotions": [{{"index": 0, "new_importance": 0.2}}]
}}"""
        return _parse_json_response(self._llm(prompt), {"add": [], "updates": [], "demotions": []})


# ── Utilities ──────────────────────────────────────────────────────────────────

def _format_trajectory(trajectory: list[dict]) -> str:
    lines = []
    for i, step in enumerate(trajectory):
        role = step.get("role", "agent")
        content = step.get("content", "")
        lines.append(f"[{i}] {role}: {content[:500]}")
    return "\n".join(lines)


def _parse_json_response(text: str, default: Any) -> Any:
    try:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group())
    except (json.JSONDecodeError, AttributeError):
        pass
    return default
